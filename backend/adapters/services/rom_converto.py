import asyncio
import contextlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any, Final, Protocol

from config import ROM_CONVERTO_ENABLED, ROM_CONVERTO_TIMEOUT
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import TITLE_ID_MAX_LENGTH
from utils.filesystem import SERVED_FILE_MODE
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

_BINARY: Final = "rom-converto"

CUE_EXT: Final = ".cue"

# Bounds one run's output, which carries every file's embedded images as JSON.
INFO_BATCH_SIZE: Final = 64

_PSP_TITLE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Z]{4}[0-9]{5}")


class RomConvertoError(Exception): ...


class RomConvertoBinaryNotFoundError(RomConvertoError): ...


class RomConvertoTimeoutError(RomConvertoError): ...


class RomConvertoOperationError(RomConvertoError):
    """A conversion command exited nonzero."""


class RomConvertoUnsafeSourceError(RomConvertoError):
    """A cue sheet references a track outside its own folder."""


# `xbox convert` keeps only a dump's game partition, so a library never stores its output.
_LOSSY_ARGV: Final[frozenset[tuple[str, ...]]] = frozenset({("xbox", "convert")})


@dataclass(frozen=True)
class RomConvertoInfo:
    # Rendered the way sigil renders the same platform's id, so either
    # extractor can fill `Rom.title_id` interchangeably.
    title_id: str | None = None
    title_version: int | None = None


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


def download_targets(platform_slug: str, file_name: str) -> list[str]:
    """The formats a download of `file_name` can be converted to, not counting the one it is stored in."""
    stored = file_format(file_name)
    targets = {op.target for op in OPERATIONS if platform_slug in op.platforms}
    return sorted(
        target
        for target in targets
        if target != stored and resolve_operation(platform_slug, target, file_name)
    )


def _cue_file_name(line: str) -> str | None:
    """The track a cue `FILE` line names, read the way the CLI reads it, or None for another line."""
    parts = line.split()
    if not parts or parts[0].upper() != "FILE":
        return None
    # The CLI takes everything between the first and last quote, or the bare second word.
    start, end = line.find('"'), line.rfind('"')
    if start != -1:
        return line[start + 1 : end] if start < end else ""
    return parts[1] if len(parts) >= 3 else ""


def cue_tracks(cue: Path) -> list[Path]:
    """The track files a cue sheet references, all beside it.

    Raises:
        RomConvertoUnsafeSourceError: A track is not a plain file name in the cue's folder.
    """
    tracks: list[Path] = []
    for line in cue.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        name = _cue_file_name(line)
        if name is None:
            continue
        # The CLI joins the name onto the cue's folder, so `..` or `/` would read any file.
        if name in ("", ".", "..") or Path(name).name != name:
            raise RomConvertoUnsafeSourceError(
                f"{cue.name} references a track outside its folder"
            )
        tracks.append(cue.with_name(name))
    return tracks


def _convert_argv(operation: Operation, src: Path, out: Path) -> list[str]:
    """The arguments running `operation` on `src`, refusing a cue that reaches outside its folder."""
    if src.name.lower().endswith(CUE_EXT):
        cue_tracks(src)
    # Absolute, since the CLI runs from its own dir.
    return [*operation.argv, os.path.abspath(src), os.path.abspath(out)]


def _listable(path: Path) -> bool:
    """Whether `info` may read `path` from a paths file, which the CLI decodes as UTF-8 and trims per line."""
    name = str(path)
    if "\n" in name or name != name.strip():
        return False
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if name.lower().endswith(CUE_EXT):
        try:
            cue_tracks(path)
        except (RomConvertoUnsafeSourceError, OSError) as exc:
            log.warning(f"Skipping rom-converto info on {path}: {exc}")
            return False
    return True


def _make_sandbox() -> tuple[Path, Path]:
    """A new empty dir to run the CLI from, and the empty config file inside it."""
    sandbox = Path(tempfile.mkdtemp(prefix="rom-converto-"))
    config = sandbox / "config.toml"
    config.touch()
    return sandbox, config


def _discard_sandbox(creating: "asyncio.Future[tuple[Path, Path]]") -> None:
    if not creating.cancelled() and creating.exception() is None:
        shutil.rmtree(creating.result()[0], ignore_errors=True)


def _tail(text: str) -> str:
    return text.strip()[-_STDERR_TAIL_BYTES:]


async def _run(argv: list[str], timeout_seconds: float) -> tuple[int, str, str]:
    """Run a rom-converto subcommand and return (returncode, stdout, stderr)."""
    binary = await asyncio.to_thread(shutil.which, _BINARY)
    if binary is None:
        raise RomConvertoBinaryNotFoundError(f"{_BINARY} binary not found on PATH")
    # The CLI reads `.env`, `rom-converto.toml` and its hash cache from the cwd and
    # home, so it runs from an empty dir with an empty config and no cache.
    creating = asyncio.ensure_future(asyncio.to_thread(_make_sandbox))
    try:
        sandbox, config = await asyncio.shield(creating)
    except asyncio.CancelledError:
        # The thread still finishes making the dir, so remove it once it has.
        creating.add_done_callback(_discard_sandbox)
        raise
    try:
        # The CLI otherwise asks api.github.com for a newer release on every run.
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--no-update-check",
            "--no-cache",
            "--config",
            str(config),
            *argv,
            cwd=sandbox,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await _communicate(proc, argv, timeout_seconds)
    finally:
        await asyncio.to_thread(shutil.rmtree, sandbox, True)


async def _communicate(
    proc: asyncio.subprocess.Process, argv: list[str], timeout_seconds: float
) -> tuple[int, str, str]:
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


def _int(value: Any) -> int | None:
    """The value when it is an int a signed BIGINT column holds, else None."""
    # A corrupt header's u64 would otherwise overflow the column and fail the row.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value < 2**63 else None


def _text(value: Any, max_length: int) -> str | None:
    """The text on one line, clipped to `max_length`, or None if empty."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.replace("\x00", "").split())
    return text[:max_length].rstrip() or None


def _first_id(data: dict[str, Any], *keys: str) -> str | None:
    """The first of `keys` holding text, clipped to the title id column."""
    for key in keys:
        if title_id := _text(data.get(key), TITLE_ID_MAX_LENGTH):
            return title_id
    return None


def _title_id(kind: str, flat: dict[str, Any]) -> str | None:
    if kind in ("dol", "rvl"):
        # Sigil keys GameCube and Wii by the hex-encoded 4-char game id.
        game_id = flat.get("game_id")
        if isinstance(game_id, str) and len(game_id) >= 4:
            return game_id[:4].encode("ascii", "replace").hex().upper()
        return None
    if kind == "wup":
        title_id_hex = _first_id(flat, "title_id_hex")
        return title_id_hex[-8:] if title_id_hex else None
    if kind == "xbox":
        # An Xbox 360 disc image carries only the `xex` header, keyed by hex.
        return _first_id(flat, "title_id_code", "title_id_hex")
    if kind == "xenon":
        return _first_id(flat, "title_id_hex")
    title_id = _first_id(flat, "application_title_id_hex", "title_id", "game_code")
    if kind in ("psp", "pbp"):
        title_id = title_id or _first_id(flat, "disc_id")
        if title_id and _PSP_TITLE_ID_PATTERN.fullmatch(title_id):
            return f"{title_id[:4]}-{title_id[4:]}"
    return title_id


def _parse_info(payload: dict[str, Any]) -> RomConvertoInfo:
    kind = str(payload.get("kind") or "")
    if kind in ("chd", "cso"):
        # rom-converto only nests a PS1/PS2 or PSP disc here.
        content = payload.get("content")
        if isinstance(content, dict) and content.get("kind") not in ("chd", "cso"):
            return _parse_info(content)
        return RomConvertoInfo()
    # Consoles nest their header (Xbox `xbe`, 360 `xex`, Switch `full`, the Wii
    # `tmd` holding its title version); top-level keys win on conflict.
    flat = dict(payload)
    for key in ("xbe", "xex", "full", "tmd"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            flat = {**nested, **flat}
    return RomConvertoInfo(
        title_id=_title_id(kind, flat),
        title_version=_int(flat.get("title_version")),
    )


class RomConvertoService:
    """Service to inspect and convert ROMs using the rom-converto CLI."""

    def __init__(self) -> None:
        self._available: bool | None = None
        # None when the manifest predates `info_extensions`: inspect everything.
        self._info_extensions: frozenset[str] | None = None
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
        """Inspect files in `info` runs of up to `INFO_BATCH_SIZE`, keyed by the paths it recognized; never raises."""
        listed = await asyncio.to_thread(lambda: [p for p in paths if _listable(p)])
        infos: dict[Path, RomConvertoInfo] = {}
        for chunk in batched(listed, INFO_BATCH_SIZE):
            infos.update(await self._read_run(list(chunk)))
        return infos

    async def _read_run(self, listed: list[Path]) -> dict[Path, RomConvertoInfo]:
        log.debug(
            f"Executing {hl('rom-converto', color=LIGHTMAGENTA)} info on {len(listed)} file(s)"
        )
        paths_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", suffix=".txt", delete=False
            ) as fh:
                paths_file = fh.name
                fh.write("".join(f"{p}\n" for p in listed))
            code, stdout, stderr = await _run(
                ["info", "--json", "--paths-file", paths_file], ROM_CONVERTO_TIMEOUT
            )
        except (RomConvertoError, OSError) as exc:
            log.warning(f"rom-converto info failed: {exc}")
            return {}
        finally:
            if paths_file is not None:
                os.unlink(paths_file)
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
        """Run `operation` on `src`, writing `out`, which must be alone in its directory.

        Raises:
            RomConvertoUnsafeSourceError: `src` is a cue sheet reaching outside its folder.
            RomConvertoOperationError: The command failed or wrote more than `out`.
        """
        argv = await asyncio.to_thread(_convert_argv, operation, src, out)
        code, stdout, stderr = await _run(argv, ROM_CONVERTO_TIMEOUT)
        if code != 0:
            diagnostic = _tail(stderr) or _tail(stdout)
            raise RomConvertoOperationError(
                f"rom-converto {' '.join(operation.argv)} failed with code {code}: {diagnostic}"
            )
        await asyncio.to_thread(_settle_output, operation, out)


_StatKey = tuple[int, int]
_ChunkInfos = dict[Path, tuple[_StatKey | None, RomConvertoInfo]]


class _InfoReader(Protocol):
    async def read_infos(self, paths: list[Path]) -> dict[Path, RomConvertoInfo]: ...


def _stat_key(path: Path) -> _StatKey | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_size, st.st_mtime_ns


class RomConvertoInfoBatch:
    """`read_infos` over a scan's known files, shared across roms in runs of `INFO_BATCH_SIZE`.

    The first request for a known file starts one run over it and the next
    unread files in scan order, so the roms after it find theirs already read.
    """

    def __init__(self, service: _InfoReader, paths: Sequence[Path]) -> None:
        self._service = service
        self._order = list(dict.fromkeys(paths))
        self._index = {path: i for i, path in enumerate(self._order)}
        self._runs: dict[Path, asyncio.Task[_ChunkInfos | None]] = {}
        # Files already handed out; asking for one again reads it directly.
        self._taken: set[Path] = set()

    def _chunk(self, requested: list[Path]) -> list[Path]:
        chunk = [path for path in requested if path not in self._runs]
        start = min(self._index[path] for path in chunk)
        for path in self._order[start:]:
            if len(chunk) >= INFO_BATCH_SIZE:
                break
            if path not in self._runs and path not in self._taken and path not in chunk:
                chunk.append(path)
        return chunk

    async def _read(self, chunk: list[Path]) -> _ChunkInfos | None:
        """The chunk's infos, or None when the run read nothing (a failed run reads nothing too)."""
        stats = await asyncio.to_thread(lambda: [_stat_key(path) for path in chunk])
        infos = await self._service.read_infos(chunk)
        if not infos:
            return None
        return {
            path: (stat, infos[path])
            for path, stat in zip(chunk, stats, strict=True)
            if path in infos
        }

    async def read_infos(self, paths: list[Path]) -> dict[Path, RomConvertoInfo]:
        """The same result `RomConvertoService.read_infos` gives, from the shared runs."""
        paths = list(dict.fromkeys(paths))
        known = [
            path for path in paths if path in self._index and path not in self._taken
        ]
        if any(path not in self._runs for path in known):
            chunk = self._chunk(known)
            run = asyncio.create_task(self._read(chunk))
            for path in chunk:
                self._runs[path] = run
        self._taken.update(known)
        unread = [path for path in paths if path not in known]
        read: list[tuple[Path, _StatKey | None, RomConvertoInfo]] = []
        for path in known:
            # Shielded so one rom's cancellation doesn't cancel the others' run.
            result = await asyncio.shield(self._runs.pop(path))
            if result is None:
                # Each rom retries on its own, so one failed run can't drop a whole chunk.
                unread.append(path)
            elif (entry := result.pop(path, None)) is not None:
                read.append((path, *entry))
        current = await asyncio.to_thread(
            lambda: [_stat_key(path) for path, _, _ in read]
        )
        infos: dict[Path, RomConvertoInfo] = {}
        for (path, stat, info), now in zip(read, current, strict=True):
            # A file rewritten since the run is read again below.
            if stat is not None and stat == now:
                infos[path] = info
            else:
                unread.append(path)
        if unread:
            infos.update(await self._service.read_infos(unread))
        return infos


rom_converto_service = RomConvertoService()
