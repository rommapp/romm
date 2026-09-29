import asyncio
import contextlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from config import (
    ROM_CONVERTO_ENABLED,
    ROM_CONVERTO_MAX_CONCURRENCY,
    ROM_CONVERTO_PATH,
    ROM_CONVERTO_TIMEOUT,
)
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from utils.platform_slugs import UniversalPlatformSlug as UPS

# Wider than the conversion targets: `info` only reads headers, so every
# platform it can pull a title id or serial from counts.
CONVERTO_PLATFORM_SLUGS: Final[frozenset[str]] = frozenset(
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
        UPS.SWITCH_2,
        UPS.XBOX,
        UPS.XBOX360,
    }
)

# The capabilities probe must never hang scan/download paths; a real
# manifest print is instant.
_PROBE_TIMEOUT_SECONDS = 30

_STDERR_TAIL_BYTES = 400


class RomConvertoError(Exception): ...


class RomConvertoBinaryNotFoundError(RomConvertoError): ...


class RomConvertoTimeoutError(RomConvertoError): ...


class RomConvertoOperationError(RomConvertoError):
    """A conversion command exited nonzero."""


@dataclass(frozen=True)
class RomConvertoInfo:
    # Rendered the way sigil renders the same platform's id, so either
    # extractor can fill `Rom.title_id` interchangeably.
    title_id: str | None
    title_version: int | None


@dataclass(frozen=True)
class Operation:
    """A subcommand bringing `input_exts` files to `target`; source and output are appended to `argv`."""

    target: str
    platforms: frozenset[str]
    argv: tuple[str, ...]
    input_exts: frozenset[str]
    output_ext: str

    def output_name(self, src: Path, input_ext: str) -> str:
        """`src` renamed from the matched lowercase `input_ext` to the output extension."""
        return f"{src.name[: len(src.name) - len(input_ext)]}{self.output_ext}"


def _op(
    target: str,
    platforms: set[UPS],
    argv: str,
    input_exts: str,
    output_ext: str,
) -> Operation:
    return Operation(
        target=target,
        platforms=frozenset(platforms),
        argv=tuple(argv.split()),
        input_exts=frozenset(input_exts.split()),
        output_ext=output_ext,
    )


_DVD_PLATFORMS = {UPS.PSP, UPS.PS2}
_CD_PLATFORMS = {UPS.PSX, UPS.SATURN, UPS.SEGACD, UPS.DC}

# The CLI's single-file format conversions. Decrypt/encrypt and directory-shaped
# operations (Wii U packs, Switch merge/split, `extract`, Xbox 360 GoD) are left out.
OPERATIONS: Final[tuple[Operation, ...]] = (
    # 3DS
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cia", ".zcia"),
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cci .3ds", ".zcci"),
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cxi", ".zcxi"),
    _op("cia", {UPS.N3DS}, "ctr decompress", ".zcia", ".cia"),
    _op("cia", {UPS.N3DS}, "ctr convert", ".3ds .cci", ".cia"),
    _op("cci", {UPS.N3DS}, "ctr decompress", ".zcci", ".cci"),
    _op("cci", {UPS.N3DS}, "ctr convert", ".cia", ".cci"),
    # Sony discs
    _op("iso", _DVD_PLATFORMS, "cso decompress", ".cso .zso .dax", ".iso"),
    # CD-mode CHDs extract to .bin/.cue, so only DVD platforms get this.
    _op("iso", _DVD_PLATFORMS, "chd extract", ".chd", ".iso"),
    _op("iso", _DVD_PLATFORMS | _CD_PLATFORMS, "cue to-iso", ".cue", ".iso"),
    _op("iso", {UPS.PSP}, "psp to-iso", ".pbp", ".iso"),
    _op("cso", _DVD_PLATFORMS, "cso compress --format cso", ".iso", ".cso"),
    _op("cso", _DVD_PLATFORMS, "chd to-cso --format cso", ".chd", ".cso"),
    _op("zso", _DVD_PLATFORMS, "cso compress --format zso", ".iso", ".zso"),
    _op("zso", _DVD_PLATFORMS, "chd to-cso --format zso", ".chd", ".zso"),
    _op("chd", _DVD_PLATFORMS | _CD_PLATFORMS, "chd compress", ".cue .iso", ".chd"),
    _op("chd", _DVD_PLATFORMS, "cso to-chd", ".cso .zso .dax", ".chd"),
    # GameCube / Wii
    _op("rvz", {UPS.NGC}, "dol compress", ".iso .gcm", ".rvz"),
    _op("rvz", {UPS.NGC}, "dol migrate", ".gcz .nkit.iso .nkit.gcz", ".rvz"),
    _op("iso", {UPS.NGC}, "dol decompress", ".rvz", ".iso"),
    _op("rvz", {UPS.WII}, "rvl compress", ".iso .wbfs", ".rvz"),
    _op("rvz", {UPS.WII}, "rvl migrate", ".wia .gcz .nkit.iso .nkit.gcz", ".rvz"),
    _op("iso", {UPS.WII}, "rvl decompress", ".rvz", ".iso"),
    _op("wbfs", {UPS.WII}, "rvl decompress", ".rvz", ".wbfs"),
    # Switch (prod.keys resolved by the CLI itself)
    _op("nsz", {UPS.SWITCH, UPS.SWITCH_2}, "nx compress", ".nsp", ".nsz"),
    _op("xcz", {UPS.SWITCH, UPS.SWITCH_2}, "nx compress", ".xci", ".xcz"),
    _op("nsp", {UPS.SWITCH, UPS.SWITCH_2}, "nx decompress", ".nsz", ".nsp"),
    _op("xci", {UPS.SWITCH, UPS.SWITCH_2}, "nx decompress", ".xcz", ".xci"),
    # Xbox
    _op("xiso", {UPS.XBOX}, "xbox convert", ".iso", ".xiso"),
    _op("zar", {UPS.XBOX360}, "xenon compress", ".iso", ".zar"),
)

# Platform slug -> the targets it can be configured with.
TARGETS_BY_PLATFORM: Final[dict[str, frozenset[str]]] = {
    slug: frozenset(op.target for op in OPERATIONS if slug in op.platforms)
    for slug in sorted({slug for op in OPERATIONS for slug in op.platforms})
}


def normalize_platform_formats(raw: dict[str, str]) -> dict[str, str]:
    """`raw` with slugs and targets trimmed and lowercased.

    Raises:
        ValueError: A platform has no conversions, or a target isn't one of them.
    """
    cleaned = {
        str(slug).strip().lower(): str(target).strip().lower()
        for slug, target in raw.items()
    }
    for slug, target in cleaned.items():
        targets = TARGETS_BY_PLATFORM.get(slug)
        if targets is None:
            raise ValueError(
                f"rom-converto has no conversions for {slug!r}. "
                f"Supported: {sorted(TARGETS_BY_PLATFORM)}."
            )
        if target not in targets:
            raise ValueError(
                f"{target!r} is not a conversion target for {slug}. "
                f"Valid options: {sorted(targets)}."
            )
    return cleaned


def resolve_operation(
    platform_slug: str, target: str, file_name: str
) -> tuple[Operation, str] | None:
    """The operation and matched extension bringing `file_name` to `target`, or None if none applies."""
    name = file_name.lower()
    best: tuple[Operation, str] | None = None
    for op in OPERATIONS:
        if op.target != target or platform_slug not in op.platforms:
            continue
        for ext in op.input_exts:
            # Prefer the longer extension so `.nkit.iso` is not read as `.iso`.
            if name.endswith(ext) and (best is None or len(ext) > len(best[1])):
                best = (op, ext)
    return best


def _tail(text: str) -> str:
    return text.strip()[-_STDERR_TAIL_BYTES:]


async def _run(argv: list[str], timeout_seconds: float) -> tuple[int, str, str]:
    """Run a rom-converto subcommand and return (returncode, stdout, stderr)."""
    binary = await asyncio.to_thread(shutil.which, ROM_CONVERTO_PATH)
    if binary is None:
        raise RomConvertoBinaryNotFoundError(
            f"rom-converto binary not found at {ROM_CONVERTO_PATH}"
        )
    # The CLI otherwise asks api.github.com for a newer release on every run.
    proc = await asyncio.create_subprocess_exec(
        binary,
        "--no-update-check",
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_seconds)
    except TimeoutError as err:
        _kill(proc)
        # Drain the pipes so the transport closes instead of leaking its fds.
        await proc.communicate()
        raise RomConvertoTimeoutError(
            f"rom-converto {' '.join(argv[:2])} timed out after {timeout_seconds}s"
        ) from err
    except BaseException:
        # A cancelled caller must not leave a conversion running unowned.
        _kill(proc)
        raise

    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _kill(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _title_id(kind: str, flat: dict[str, Any]) -> str | None:
    if kind in ("dol", "rvl"):
        # Sigil keys GameCube and Wii by the hex-encoded 4-char game id.
        game_id = flat.get("game_id")
        if isinstance(game_id, str) and len(game_id) >= 4:
            return game_id[:4].encode("ascii", "replace").hex().upper()
        return None
    if kind == "wup":
        title_id_hex = flat.get("title_id_hex")
        return title_id_hex[-8:] if isinstance(title_id_hex, str) else None
    if kind == "xbox":
        return _first_str(flat, "title_id_code")
    if kind == "xenon":
        return _first_str(flat, "title_id_hex")
    return _first_str(flat, "application_title_id_hex", "title_id", "game_code")


def _parse_info(payload: dict[str, Any]) -> RomConvertoInfo:
    # Consoles nest their header (Xbox `xbe`, 360 `xex`, Switch `full`,
    # CHD/CSO inner disc `content`); top-level keys win on conflict.
    flat = dict(payload)
    for key in ("xbe", "xex", "full", "content"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            flat = {**nested, **flat}
    kind = str(flat.get("kind") or "")
    title_version = flat.get("title_version")
    return RomConvertoInfo(
        title_id=_title_id(kind, flat),
        title_version=title_version if isinstance(title_version, int) else None,
    )


class RomConvertoService:
    """Service to inspect and convert ROMs using the rom-converto CLI."""

    def __init__(self) -> None:
        self._available: bool | None = None
        # None when the manifest predates `info_extensions`: inspect everything.
        self._info_extensions: frozenset[str] | None = None
        self._probe_lock = asyncio.Lock()
        # Each conversion reads and writes whole disc images.
        self._convert_semaphore = asyncio.Semaphore(ROM_CONVERTO_MAX_CONCURRENCY)

    async def is_enabled(self) -> bool:
        if not ROM_CONVERTO_ENABLED:
            return False
        async with self._probe_lock:
            if self._available is not None:
                return self._available
            # A corrupt or wrong-arch binary passes which(); a missing one
            # stays uncached so installing it needs no restart.
            failure: str | None
            try:
                code, stdout, _ = await _run(["capabilities"], _PROBE_TIMEOUT_SECONDS)
            except RomConvertoBinaryNotFoundError:
                return False
            except (RomConvertoTimeoutError, OSError) as exc:
                failure = str(exc)
            else:
                failure = f"code {code}" if code != 0 else None
            if failure is not None:
                log.warning(
                    f"rom-converto at {hl(ROM_CONVERTO_PATH)} failed its capability "
                    f"probe ({failure}); disabling integration until restart"
                )
                self._available = False
                return False
            try:
                manifest = json.loads(stdout)
            except json.JSONDecodeError:
                manifest = {}
            if not isinstance(manifest, dict):
                manifest = {}
            version = manifest.get("version") or "unknown version"
            extensions = manifest.get("info_extensions")
            if isinstance(extensions, list):
                self._info_extensions = frozenset(
                    f".{ext.lower()}" for ext in extensions if isinstance(ext, str)
                )
            log.info(
                f"Detected {hl('rom-converto', color=LIGHTMAGENTA)} {hl(str(version))}"
            )
            self._available = True
            return True

    def can_inspect(self, path: Path) -> bool:
        """Whether `info` recognizes this file's extension."""
        if self._info_extensions is None:
            return True
        return path.suffix.lower() in self._info_extensions

    async def read_infos(self, paths: list[Path]) -> dict[Path, RomConvertoInfo]:
        """Inspect files in one `info --paths-file` run, keyed by the paths it recognized; never raises."""
        # The paths file is line-based, so a name holding a newline can't be listed.
        paths = [p for p in paths if "\n" not in str(p)]
        if not paths:
            return {}
        log.debug(
            f"Executing {hl('rom-converto', color=LIGHTMAGENTA)} info on {len(paths)} file(s)"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("".join(f"{p}\n" for p in paths))
        try:
            code, stdout, stderr = await _run(
                ["info", "--json", "--paths-file", fh.name], ROM_CONVERTO_TIMEOUT
            )
        except (RomConvertoError, OSError) as exc:
            log.warning(f"rom-converto info failed: {exc}")
            return {}
        finally:
            os.unlink(fh.name)
        if code != 0:
            log.warning(f"rom-converto info failed (code {code}): {_tail(stderr)}")
            return {}
        try:
            records = json.loads(stdout)
        except json.JSONDecodeError:
            log.warning("rom-converto info returned non-JSON output")
            return {}
        if not isinstance(records, list):
            return {}

        infos: dict[Path, RomConvertoInfo] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            payload = record.get("info")
            if record.get("ok") and isinstance(payload, dict):
                infos[Path(str(record.get("path")))] = _parse_info(payload)
            else:
                log.debug(
                    f"rom-converto did not recognize {record.get('path')}: "
                    f"{record.get('error')}"
                )
        return infos

    async def convert(self, operation: Operation, src: Path, out: Path) -> None:
        """Run `operation` on `src`, writing `out`."""
        argv = [*operation.argv, str(src), str(out)]
        async with self._convert_semaphore:
            code, stdout, stderr = await _run(argv, ROM_CONVERTO_TIMEOUT)
        if code != 0:
            diagnostic = _tail(stderr) or _tail(stdout)
            raise RomConvertoOperationError(
                f"rom-converto {' '.join(operation.argv)} failed with code {code}: {diagnostic}"
            )


rom_converto_service = RomConvertoService()
