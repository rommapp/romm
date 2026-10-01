import asyncio
import contextlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from config import ROM_CONVERTO_ENABLED, ROM_CONVERTO_TIMEOUT
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from utils.filesystem import SERVED_FILE_MODE
from utils.platform_slugs import UniversalPlatformSlug as UPS

# The capabilities probe must never hang download paths; a real
# manifest print is instant.
_PROBE_TIMEOUT_SECONDS = 30

_STDERR_TAIL_BYTES = 400

_BINARY: Final = "rom-converto"


class RomConvertoError(Exception): ...


class RomConvertoBinaryNotFoundError(RomConvertoError): ...


class RomConvertoTimeoutError(RomConvertoError): ...


class RomConvertoOperationError(RomConvertoError):
    """A conversion command exited nonzero."""


# `xbox convert` keeps only a dump's game partition, so a library never stores its output.
_LOSSY_ARGV: Final[frozenset[tuple[str, ...]]] = frozenset({("xbox", "convert")})


@dataclass(frozen=True)
class Operation:
    """A subcommand bringing `input_exts` files to `target`; source and output are appended to `argv`."""

    target: str
    platforms: frozenset[str]
    argv: tuple[str, ...]
    input_exts: frozenset[str]
    output_ext: str

    @property
    def lossless(self) -> bool:
        return self.argv not in _LOSSY_ARGV

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
    _op("iso", _DVD_PLATFORMS, "cue to-iso", ".cue", ".iso"),
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

# Targets that store the image as-is, so converting to one can grow the file.
UNCOMPRESSED_TARGETS: Final[frozenset[str]] = frozenset(
    {"cci", "cia", "iso", "nsp", "wbfs", "xci", "xiso"}
)


# Platform slug -> the targets a library can be stored in.
LIBRARY_TARGETS_BY_PLATFORM: Final[dict[str, frozenset[str]]] = {
    slug: frozenset(
        op.target for op in OPERATIONS if slug in op.platforms and op.lossless
    )
    for slug in sorted(
        {slug for op in OPERATIONS if op.lossless for slug in op.platforms}
    )
}


def _download_formats() -> dict[str, dict[str, list[str]]]:
    table: dict[str, dict[str, set[str]]] = {}
    for op in OPERATIONS:
        for slug in op.platforms:
            for ext in op.input_exts:
                table.setdefault(slug, {}).setdefault(ext, set()).add(op.target)
    return {
        slug: {ext: sorted(targets) for ext, targets in sorted(exts.items())}
        for slug, exts in sorted(table.items())
    }


# Platform slug -> input extension -> the targets a download of it can be converted to.
DOWNLOAD_FORMATS: Final[dict[str, dict[str, list[str]]]] = _download_formats()


# Extensions whose format goes by another name than the extension itself.
_FORMAT_ALIASES: Final[dict[str, str]] = {
    ".3ds": "cci",
    ".gcm": "iso",
    ".zcci": "z3ds",
    ".zcia": "z3ds",
    ".zcxi": "z3ds",
}
_KNOWN_EXTS: Final[frozenset[str]] = frozenset(
    {ext for op in OPERATIONS for ext in (*op.input_exts, op.output_ext)}
    | _FORMAT_ALIASES.keys()
)


def file_format(file_name: str) -> str:
    """The format `file_name` is in, as a target name or its extension (`nkit-iso`)."""
    name = file_name.lower()
    ext = max((e for e in _KNOWN_EXTS if name.endswith(e)), key=len, default=None)
    if ext is None:
        return Path(name).suffix.lstrip(".")
    return _FORMAT_ALIASES.get(ext, ext.lstrip(".").replace(".", "-"))


def canonical_format(name: str) -> str:
    """The target name a client means by `name`, so `3ds` reads as `cci`."""
    return _FORMAT_ALIASES.get(f".{name}", name)


def normalize_platform_formats(raw: dict[str, str]) -> dict[str, str]:
    """`raw` with slugs and library targets trimmed and lowercased.

    Raises:
        ValueError: A platform has no library targets, or a target isn't one of them.
    """
    cleaned = {
        str(slug).strip().lower(): str(target).strip().lower()
        for slug, target in raw.items()
    }
    for slug, target in cleaned.items():
        targets = LIBRARY_TARGETS_BY_PLATFORM.get(slug)
        if targets is None:
            raise ValueError(
                f"rom-converto has no library formats for {slug!r}. "
                f"Supported: {sorted(LIBRARY_TARGETS_BY_PLATFORM)}."
            )
        if target not in targets:
            raise ValueError(
                f"{target!r} is not a conversion target for {slug}. "
                f"Valid options: {sorted(targets)}."
            )
    return cleaned


def resolve_operation(
    platform_slug: str, target: str, file_name: str, *, lossless: bool = False
) -> tuple[Operation, str] | None:
    """The operation and matched extension bringing `file_name` to `target`, or None if none applies."""
    name = file_name.lower()
    best: tuple[Operation, str] | None = None
    for op in OPERATIONS:
        if op.target != target or platform_slug not in op.platforms:
            continue
        if lossless and not op.lossless:
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
    binary = await asyncio.to_thread(shutil.which, _BINARY)
    if binary is None:
        raise RomConvertoBinaryNotFoundError(f"{_BINARY} binary not found on PATH")
    # The CLI otherwise asks api.github.com for a newer release on every run.
    proc = await asyncio.create_subprocess_exec(
        binary,
        "--no-update-check",
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
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


def _settle_output(operation: Operation, out: Path) -> None:
    """Check `out` is all the command wrote beside it, and make it servable."""
    if [p.name for p in out.parent.iterdir()] != [out.name]:
        raise RomConvertoOperationError(
            f"rom-converto {' '.join(operation.argv)} did not write exactly {out.name}"
        )
    # rom-converto may write an owner-only file, which nginx can't serve.
    out.chmod(SERVED_FILE_MODE)


def _kill(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


class RomConvertoService:
    """Service to convert ROMs using the rom-converto CLI."""

    def __init__(self) -> None:
        self._available: bool | None = None
        self._probe_lock = asyncio.Lock()

    async def is_enabled(self) -> bool:
        if not ROM_CONVERTO_ENABLED:
            return False
        if self._available is not None:
            return self._available
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
                    f"{hl(_BINARY)} failed its capability "
                    f"probe ({failure}); disabling integration until restart"
                )
                self._available = False
                return False
            try:
                manifest = json.loads(stdout)
            except json.JSONDecodeError:
                manifest = None
            version = (
                manifest.get("version") if isinstance(manifest, dict) else None
            ) or "unknown version"
            log.info(
                f"Detected {hl('rom-converto', color=LIGHTMAGENTA)} {hl(str(version))}"
            )
            self._available = True
            return True

    async def convert(self, operation: Operation, src: Path, out: Path) -> None:
        """Run `operation` on `src`, writing `out`, which must be alone in its directory.

        Raises:
            RomConvertoOperationError: The command failed or wrote more than `out`.
        """
        argv = [*operation.argv, str(src), str(out)]
        code, stdout, stderr = await _run(argv, ROM_CONVERTO_TIMEOUT)
        if code != 0:
            diagnostic = _tail(stderr) or _tail(stdout)
            raise RomConvertoOperationError(
                f"rom-converto {' '.join(operation.argv)} failed with code {code}: {diagnostic}"
            )
        await asyncio.to_thread(_settle_output, operation, out)


rom_converto_service = RomConvertoService()
