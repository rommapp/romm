import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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

# Platform slugs whose files rom-converto's `info` can identify with a
# title id or serial. Wider than the conversion targets on purpose:
# extraction only reads headers, so every inspector counts.
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
    """A conversion command exited nonzero; carries the CLI's diagnostic."""

    def __init__(self, message: str, returncode: int, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True)
class RomConvertoInfo:
    kind: str
    # Rendered the way sigil renders the same platform's id, so either
    # extractor can fill `Rom.title_id` interchangeably.
    title_id: str | None
    title_version: int | None


@dataclass(frozen=True)
class Operation:
    """One rom-converto subcommand that turns a file of `input_exts` into
    the `target` format. `argv` is the subcommand plus fixed flags; the
    source and output paths are appended positionally."""

    target: str
    platforms: frozenset[str]
    argv: tuple[str, ...]
    input_exts: frozenset[str]
    # None keeps the input's extension (decrypt/encrypt rewrite in place).
    output_ext: str | None

    def output_name(self, src: Path, input_ext: str) -> str:
        """`src` renamed to the output extension; `input_ext` is the
        lowercased extension `resolve_operation` matched."""
        cut = len(src.name) - len(input_ext)
        return f"{src.name[:cut]}{self.output_ext or src.name[cut:]}"


def _op(
    target: str,
    platforms: set[str],
    argv: str,
    input_exts: str,
    output_ext: str | None,
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

# Every single-file operation the CLI offers, keyed by the target a platform
# can be configured with. Directory-shaped operations (Wii U packs, Switch
# merge/split, the `extract` family, Xbox 360 GoD) have no single output
# file to serve, so they are not here.
OPERATIONS: Final[tuple[Operation, ...]] = (
    # 3DS
    _op("decrypted", {UPS.N3DS}, "ctr decrypt", ".cia .3ds .cci .cxi", None),
    _op("encrypted", {UPS.N3DS}, "ctr encrypt", ".cia .3ds .cci .cxi", None),
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cia", ".zcia"),
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cci .3ds", ".zcci"),
    _op("z3ds", {UPS.N3DS}, "ctr compress", ".cxi", ".zcxi"),
    _op("cia", {UPS.N3DS}, "ctr decompress", ".zcia", ".cia"),
    _op("cia", {UPS.N3DS}, "ctr convert", ".3ds .cci", ".cia"),
    _op("cci", {UPS.N3DS}, "ctr decompress", ".zcci", ".cci"),
    _op("cci", {UPS.N3DS}, "ctr convert", ".cia", ".cci"),
    # NDS
    _op("decrypted", {UPS.NDS}, "nds decrypt", ".nds", None),
    _op("encrypted", {UPS.NDS}, "nds encrypt", ".nds", None),
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
    _op("decrypted", {UPS.PS3}, "ps3 decrypt", ".iso", None),
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


def resolve_operation(
    platform_slug: str, target: str, file_name: str
) -> tuple[Operation, str] | None:
    """The operation that brings `file_name` to `target` on this platform,
    with the input extension it matched, or None when the file is already
    there or no subcommand accepts it."""
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
    proc = await asyncio.create_subprocess_exec(
        binary,
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_seconds)
    except TimeoutError as err:
        proc.kill()
        # Drain the pipes so the transport closes instead of leaking its fds.
        await proc.communicate()
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


def _title_id(kind: str, flat: dict) -> str | None:
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


def _parse_info(payload: dict) -> RomConvertoInfo:
    # `kind` is the serde tag of InfoResult. Consoles nest their header
    # (Xbox `xbe`, 360 `xex`, Switch `full`, CHD/CSO inner disc `content`);
    # top-level keys win on conflict.
    flat = dict(payload)
    for key in ("xbe", "xex", "full", "content"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            flat = {**nested, **flat}
    kind = str(flat.get("kind") or "")
    title_version = flat.get("title_version")
    return RomConvertoInfo(
        kind=kind,
        title_id=_title_id(kind, flat),
        title_version=title_version if isinstance(title_version, int) else None,
    )


class RomConvertoService:
    """Service to inspect and convert ROMs using the rom-converto CLI."""

    def __init__(self) -> None:
        self._available: bool | None = None
        self._probe_lock = asyncio.Lock()
        # Each conversion reads and writes whole disc images.
        self._convert_semaphore = asyncio.Semaphore(ROM_CONVERTO_MAX_CONCURRENCY)

    async def is_enabled(self) -> bool:
        if not ROM_CONVERTO_ENABLED:
            return False
        async with self._probe_lock:
            if self._available is not None:
                return self._available
            # A stale, corrupt, or wrong-arch binary passes which(); prove it
            # runs once with the cheap capabilities manifest. A missing binary
            # stays uncached so the integration picks it up without a restart.
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
            try:
                version = json.loads(stdout)["version"]
            except (json.JSONDecodeError, KeyError, TypeError):
                version = "unknown version"
            log.info(
                f"Detected {hl('rom-converto', color=LIGHTMAGENTA)} {hl(str(version))}"
            )
            self._available = True
            return True

    async def read_info(self, path: Path) -> RomConvertoInfo | None:
        """Inspect a ROM with `rom-converto info --json`, or None when the
        tool does not recognize the file."""
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

    async def convert(self, operation: Operation, src: Path, out: Path) -> None:
        """Run `operation` on `src`, writing `out`. Bounded by the service
        semaphore and ROM_CONVERTO_TIMEOUT."""
        argv = [*operation.argv, str(src), str(out)]
        async with self._convert_semaphore:
            code, stdout, stderr = await _run(argv, ROM_CONVERTO_TIMEOUT)
        if code != 0:
            diagnostic = _tail(stderr) or _tail(stdout)
            raise RomConvertoOperationError(
                f"rom-converto {' '.join(operation.argv)} failed with code {code}: {diagnostic}",
                returncode=code,
                stderr=stderr,
            )


rom_converto_service = RomConvertoService()
