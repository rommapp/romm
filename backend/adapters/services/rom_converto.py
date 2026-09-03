import asyncio
import contextlib
import json
import shutil
from pathlib import Path

from config import (
    ROM_CONVERTO_ENABLED,
    ROM_CONVERTO_MAX_CONCURRENCY,
    ROM_CONVERTO_PATH,
    ROM_CONVERTO_TIMEOUT,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import (
    RomConvertoContainer,
    RomConvertoImage,
    RomConvertoMetadata,
)

# TODO: batch `info` exists in rom-converto >= 0.21 (`info --paths-file`);
# wire it up if scan extraction ever moves to per-platform batching.

# Platform slugs whose files rom-converto's `info` can identify with a
# title id or serial. Wider than the conversion target list on purpose:
# extraction only reads headers, so every inspector counts.
CONVERTO_PLATFORM_SLUGS: frozenset[str] = frozenset(
    {
        UPS.N3DS,
        UPS.NDS,
        UPS.PSP,
        UPS.PSVITA,
        UPS.PSX,
        UPS.PS2,
        UPS.PS3,
        UPS.NGC,
        UPS.WII,
        UPS.WIIU,
        UPS.SWITCH,
        UPS.DC,
        UPS.SATURN,
        UPS.SEGACD,
        UPS.XBOX,
        UPS.XBOX360,
    }
)

# Bound concurrent conversion subprocesses, each of which reads/writes
# whole disc images.
_convert_semaphore = asyncio.Semaphore(ROM_CONVERTO_MAX_CONCURRENCY)

# The capabilities probe must never hang scan/download paths; a real
# manifest print is instant.
_PROBE_TIMEOUT_SECONDS = 30

# Disc header magics the CLI's `info` uses to split the shared .iso
# extension between the GameCube (dol) and Wii (rvl) command families.
_DOL_MAGIC = b"\xc2\x33\x9f\x3d"  # at 0x1C
_RVL_MAGIC = b"\x5d\x1c\x9e\xa3"  # at 0x18

_STDERR_TAIL_BYTES = 400


class RomConvertoError(Exception): ...


class RomConvertoBinaryNotFoundError(RomConvertoError): ...


class RomConvertoTimeoutError(RomConvertoError): ...


class RomConvertoUnsupportedError(RomConvertoError): ...


class RomConvertoOperationError(RomConvertoError):
    """A conversion command exited nonzero; carries the CLI's diagnostic."""

    def __init__(self, message: str, returncode: int, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


# The parsed shape is owned by the model layer (not persisted there yet).
RomConvertoInfo = RomConvertoMetadata


def _tail(text: str) -> str:
    return text.strip()[-_STDERR_TAIL_BYTES:]


async def _run(argv: list[str], timeout_seconds: float) -> tuple[int, str, str]:
    """Run a rom-converto subcommand and return (returncode, stdout, stderr)."""
    binary = await asyncio.to_thread(shutil.which, ROM_CONVERTO_PATH)
    if binary is None:
        raise RomConvertoBinaryNotFoundError(
            f"rom-converto binary not found at {ROM_CONVERTO_PATH}"
        )
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise RomConvertoBinaryNotFoundError(
            f"rom-converto binary not found at {ROM_CONVERTO_PATH}"
        ) from e

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_seconds)
    except TimeoutError as err:
        proc.kill()
        await proc.wait()
        raise RomConvertoTimeoutError(
            f"rom-converto {' '.join(argv[:2])} timed out after {timeout_seconds}s"
        ) from err

    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _first_str(data: dict, *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _parse_names(payload: dict) -> dict[str, str]:
    """Collect per-language names from whatever shape this console carries:
    3DS SMDH title tables, Wii IMET blocks, or a plain title string."""
    names: dict[str, str] = {}
    smdh = payload.get("smdh")
    if isinstance(smdh, dict):
        for title in smdh.get("titles") or []:
            if isinstance(title, dict) and title.get("short_description"):
                names[title.get("language") or ""] = title["short_description"]
    imet = payload.get("imet_names")
    if isinstance(imet, dict):
        for entry in imet.get("entries") or []:
            if isinstance(entry, (list, tuple)) and len(entry) == 2 and entry[1]:
                names[entry[0] or ""] = entry[1]
    if not names:
        fallback = _first_str(
            payload,
            "game_name",
            "title",
            "game_title",
            "title_name",
            "overseas_title",
            "domestic_title",
        )
        if fallback:
            names[""] = fallback
    return names


def _flatten(payload: dict) -> dict:
    """Merge nested metadata blocks (xbox `xbe`, 360 `xex`, retro `details`)
    into one lookup dict; top-level keys win on conflict."""
    flat: dict = dict(payload)
    for key in ("xbe", "xex", "details"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            flat = {**nested, **flat}
    return flat


def _parse_image(value: object) -> RomConvertoImage | None:
    """Decode an Image payload: {png_bytes: [n, ...], width, height}."""
    if not isinstance(value, dict):
        return None
    raw = value.get("png_bytes")
    width, height = value.get("width"), value.get("height")
    if (
        not isinstance(raw, list)
        or not isinstance(width, int)
        or not isinstance(height, int)
    ):
        return None
    return RomConvertoImage(
        width=width, height=height, png=bytes(n & 0xFF for n in raw)
    )


def _parse_icons(flat: dict) -> dict[str, RomConvertoImage]:
    """Collect embedded images under their source names: icon, small_icon,
    banner (banner_image/image on dol/rvl), pic0, pic1."""
    icons: dict[str, RomConvertoImage] = {}
    for key in (
        "icon",
        "small_icon",
        "banner",
        "banner_image",
        "pic0",
        "pic1",
        "image",
    ):
        image = _parse_image(flat.get(key))
        if image is not None:
            name = "banner" if key in ("banner", "banner_image", "image") else key
            icons.setdefault(name, image)
    return icons


def _parse_publisher(flat: dict) -> str | None:
    publisher = _first_str(flat, "publisher", "maker_name")
    if publisher:
        return publisher
    publishers = flat.get("publishers")
    if isinstance(publishers, list):
        return next((p for p in publishers if isinstance(p, str) and p), None)
    return None


def _parse_container(kind: str, flat: dict) -> RomConvertoContainer | None:
    """Container/compression facts, whatever the console reports: CHD/CSO
    carry full stats, disc kinds name their container (rvz, wbfs, ...),
    Switch names its kind, ZAR reports both sizes."""

    def container(
        *,
        kind: str = kind,
        format: str | None = None,
        compression: str | None = None,
        compression_ratio: float | None = None,
        physical_bytes: int | None = None,
        logical_bytes: int | None = None,
    ) -> RomConvertoContainer:
        return RomConvertoContainer(
            kind=kind,
            format=format,
            compression=compression,
            compression_ratio=compression_ratio,
            physical_bytes=physical_bytes,
            logical_bytes=logical_bytes,
        )

    if kind == "chd":
        compressors = flat.get("compressors")
        header_version = (
            f"CHD v{flat['version']}"
            if isinstance(flat.get("version"), int)
            else flat.get("version_string")
        )
        return container(
            format=header_version if isinstance(header_version, str) else None,
            compression=(
                ", ".join(compressors) if isinstance(compressors, list) else None
            ),
            compression_ratio=(
                flat.get("compression_ratio")
                if isinstance(flat.get("compression_ratio"), (int, float))
                else None
            ),
            physical_bytes=flat.get("physical_bytes"),
            logical_bytes=flat.get("logical_bytes"),
        )
    if kind == "cso":
        fmt = _first_str(flat, "format")
        return container(
            kind=(fmt or "cso").lower(),
            format=(
                f"{fmt} v{flat['version']}"
                if fmt and isinstance(flat.get("version"), int)
                else fmt
            ),
            compression_ratio=(
                flat.get("compression_ratio")
                if isinstance(flat.get("compression_ratio"), (int, float))
                else None
            ),
            physical_bytes=flat.get("physical_bytes"),
            logical_bytes=flat.get("uncompressed_size"),
        )
    if kind == "xenon":
        logical, compressed = flat.get("logical_size"), flat.get("compressed_size")
        ratio = (
            compressed / logical * 100
            if isinstance(logical, int) and isinstance(compressed, int) and logical
            else None
        )
        return container(
            kind="zar",
            compression_ratio=ratio,
            physical_bytes=compressed,
            logical_bytes=logical,
        )
    container_str = _first_str(flat, "container")
    if container_str:
        return container(
            kind=container_str.lower(), physical_bytes=flat.get("physical_bytes")
        )
    nx_kind = flat.get("container_kind")
    if isinstance(nx_kind, str):
        return container(
            kind=nx_kind.lower(), physical_bytes=flat.get("physical_bytes")
        )
    ctr_format = _first_str(flat, "format")
    if ctr_format:
        return container(
            kind=ctr_format.lower(), physical_bytes=flat.get("physical_bytes")
        )
    return None


def _parse_info(payload: dict) -> RomConvertoInfo:
    # `kind` is the serde tag of InfoResult (dol, rvl, ctr, psx, psp, ps3,
    # nds, retro, pbp, vpk, pkg, ...). Field names vary per console, so every
    # lookup is defensive. `version` is only taken when a string: CHD/CSO/PBP
    # carry an integer container version.
    flat = _flatten(payload)
    encrypted: bool | None = None
    for key in ("ncch_encrypted", "encrypted"):
        value = flat.get(key)
        if isinstance(value, bool):
            encrypted = value
            break
    return RomConvertoInfo(
        kind=str(flat.get("kind") or ""),
        title_id=_first_str(flat, "title_id_hex", "title_id", "game_id"),
        serial=_first_str(
            flat,
            "product_code",
            "serial",
            "game_id",
            "product_number",
            "disc_id",
            "game_code",
            "title_id_code",
        ),
        names=_parse_names(flat),
        publisher=_parse_publisher(flat),
        region=_first_str(flat, "region"),
        version=_first_str(flat, "version"),
        content_kind=_first_str(flat, "content_kind"),
        encrypted=encrypted,
        icons=_parse_icons(flat),
        container=_parse_container(kind=str(flat.get("kind") or ""), flat=flat),
    )


def _sniff_dol_rvl(path: Path) -> str:
    """Read the disc header magic to split .iso inputs between the dol
    (GameCube) and rvl (Wii) command families, like the CLI's `info` does."""
    with path.open("rb") as f:
        f.seek(0x18)
        if f.read(4) == _RVL_MAGIC:
            return "rvl"
        f.seek(0x1C)
        if f.read(4) == _DOL_MAGIC:
            return "dol"
    raise RomConvertoUnsupportedError(
        f"could not detect a GameCube or Wii disc in {path}"
    )


async def _build_convert_argv(
    target: str, src: Path, dest_dir: Path
) -> tuple[list[str], Path]:
    """Map a v1 target slug + input extension to the CLI subcommand and
    output path. Raises RomConvertoUnsupportedError for unknown combos."""
    suffix = src.suffix.lower()

    if target == "cia-decrypted":
        if suffix not in (".cia", ".3ds", ".cci", ".cxi"):
            raise RomConvertoUnsupportedError(
                f"target 'cia-decrypted' does not accept {suffix} input"
            )
        out = dest_dir / f"{src.stem}{suffix}"
        return ["ctr", "decrypt", str(src), str(out)], out

    if target == "iso":
        out = dest_dir / f"{src.stem}.iso"
        if suffix in (".cso", ".zso"):
            return ["cso", "decompress", str(src), str(out)], out
        if suffix == ".chd":
            # DVD-mode CHDs (PSP/PS2) extract to .iso; CD-mode CHDs extract
            # to .bin + .cue instead, so this only fits DVD-mode inputs.
            return ["chd", "extract", str(src), str(out)], out
        raise RomConvertoUnsupportedError(
            f"target 'iso' does not accept {suffix} input"
        )

    if target == "chd":
        if suffix in (".iso", ".cue"):
            out = dest_dir / f"{src.stem}.chd"
            return ["chd", "compress", str(src), str(out)], out
        raise RomConvertoUnsupportedError(
            f"target 'chd' does not accept {suffix} input"
        )

    if target == "rvz":
        out = dest_dir / f"{src.stem}.rvz"
        if suffix == ".wbfs":
            return ["rvl", "compress", str(src), str(out)], out
        if suffix == ".wia":
            return ["rvl", "migrate", str(src), str(out)], out
        if suffix == ".gcm":
            return ["dol", "compress", str(src), str(out)], out
        if suffix == ".gcz":
            # GCZ is accepted on both consoles and the container doesn't
            # record which, so route it through the GameCube family.
            return ["dol", "migrate", str(src), str(out)], out
        if suffix == ".iso":
            family = await asyncio.to_thread(_sniff_dol_rvl, src)
            return [family, "compress", str(src), str(out)], out
        raise RomConvertoUnsupportedError(
            f"target 'rvz' does not accept {suffix} input"
        )

    if target == "nsp":
        if suffix in (".nsz", ".xcz"):
            out = dest_dir / f"{src.stem}.nsp"
            return ["nx", "decompress", str(src), "-o", str(out)], out
        raise RomConvertoUnsupportedError(
            f"target 'nsp' does not accept {suffix} input"
        )

    if target == "iso-decrypted":
        if suffix == ".iso":
            out = dest_dir / f"{src.stem}.iso"
            return ["ps3", "decrypt", str(src), str(out)], out
        raise RomConvertoUnsupportedError(
            f"target 'iso-decrypted' does not accept {suffix} input"
        )

    raise RomConvertoUnsupportedError(f"unknown rom-converto target: {target}")


class RomConvertoService:
    """Service to convert ROMs and disc images using the rom-converto CLI."""

    def __init__(self) -> None:
        self._available: bool | None = None

    async def is_enabled(self) -> bool:
        if not ROM_CONVERTO_ENABLED:
            return False
        if self._available is not None:
            return self._available
        # A stale, corrupt, or wrong-arch binary passes which(); prove it
        # actually runs once with the cheap capabilities manifest and log
        # the detected version. A missing binary stays uncached so the
        # integration picks it up without a restart.
        try:
            code, stdout, _ = await _run(["capabilities"], _PROBE_TIMEOUT_SECONDS)
        except RomConvertoBinaryNotFoundError:
            return False
        if code != 0:
            log.warning(
                f"rom-converto at {hl(ROM_CONVERTO_PATH)} failed its capability "
                f"probe (code {code}); disabling integration until restart"
            )
            self._available = False
            return False
        with contextlib.suppress(json.JSONDecodeError, KeyError, TypeError):
            version = json.loads(stdout)["version"]
            log.info(
                f"Detected {hl('rom-converto', color=LIGHTMAGENTA)} {hl(str(version))}"
            )
        self._available = True
        return True

    async def read_info(self, path: Path) -> RomConvertoInfo | None:
        """Inspect a ROM or disc image with `rom-converto info --json`.

        Returns None when the tool does not recognize the file (nonzero exit
        or non-JSON output), so callers can treat unsupported input as
        "no metadata" rather than an error.
        """
        log.debug(
            f"Executing {hl('rom-converto', color=LIGHTMAGENTA)} info on {hl(str(path))}"
        )
        code, stdout, stderr = await _run(
            ["info", "--json", str(path)], ROM_CONVERTO_TIMEOUT
        )
        if code != 0:
            log.debug(
                f"rom-converto info did not recognize {path} (code {code}): {_tail(stderr)}"
            )
            return None
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            log.debug(f"rom-converto info returned non-JSON output for {path}")
            return None
        if not isinstance(payload, dict):
            return None
        return _parse_info(payload)

    async def convert(self, target: str, src: Path, dest_dir: Path) -> Path:
        """Convert `src` into `dest_dir` with the CLI subcommand for `target`,
        returning the output path. Conversions are bounded by the module
        semaphore and ROM_CONVERTO_TIMEOUT."""
        argv, out_path = await _build_convert_argv(target, src, dest_dir)
        async with _convert_semaphore:
            code, stdout, stderr = await _run(argv, ROM_CONVERTO_TIMEOUT)
        if code != 0:
            diagnostic = _tail(stderr) or _tail(stdout)
            raise RomConvertoOperationError(
                f"rom-converto {' '.join(argv[:2])} failed with code {code}: {diagnostic}",
                returncode=code,
                stderr=stderr,
            )
        return out_path


rom_converto_service = RomConvertoService()
