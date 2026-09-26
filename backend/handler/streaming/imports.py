"""Folding a foreign-emulator save or state pick into the one archive a
launch's `activate` call sends, under `.import/<kind>/` for the broker to place.
"""

import asyncio
import io
import json
import stat
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

from handler.filesystem import fs_asset_handler
from handler.streaming import broker, saves, states, webstation
from handler.streaming.config import ResolvedContainer, emulator_labels
from logger.logger import log
from models.assets import Save, State
from models.rom import Rom
from utils.zip_cache import ensure_zipfile_writable

_MANIFEST_NAME = ".broker-manifest.json"

# Charged on each entry's expanded size, so a small, highly compressible
# upload cannot inflate past the ceiling any stored save archive has.
_MAX_EXPANDED_BYTES = broker.SAVE_FILE_MAX_BYTES
_MAX_MEMBERS = 2000
_READ_CHUNK = 64 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ForeignMember:
    """One foreign pick's bytes, waiting to be folded into the import archive."""

    kind: Literal["save", "state"]
    name: str
    content: bytes
    origin: str


def origin_of(emulator: str | None, origin_device_id: str | None) -> str:
    """The advisory manifest origin of a pick; EmulatorJS records its core's name as `emulator`."""
    if origin_device_id is not None:
        return "hardware"
    if not emulator:
        return "unknown"
    return "standalone" if emulator.lower() in emulator_labels() else "emulatorjs"


def _safe_name(name: str) -> str | None:
    """None when this zip member is junk that must never ride in an import
    archive (a dotfile, or macOS's resource-fork sidecar folder)."""
    normalized = name.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    if not parts or parts[0] == "__MACOSX" or any(p.startswith(".") for p in parts):
        return None
    return "/".join(parts)


def _utf8_zipinfo(name: str, source: zipfile.ZipInfo | None) -> zipfile.ZipInfo:
    """A member header named `name`, keeping a copied entry's timestamp and mode."""
    if source is None:
        info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    else:
        info = zipfile.ZipInfo(name, date_time=source.date_time)
        # Only the permission bits, so a symlink entry lands as a regular file.
        info.external_attr = (
            stat.S_IFREG | stat.S_IMODE(source.external_attr >> 16)
        ) << 16
    info.flag_bits |= 0x800  # UTF-8 filename flag
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _read_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo | str) -> bytes:
    """An entry's bytes, inflated a chunk at a time so a size the header
    understates fails the CRC check before it can exhaust memory."""
    out = bytearray()
    with zf.open(info) as f:
        while chunk := f.read(_READ_CHUNK):
            out += chunk
    return bytes(out)


def _manifest_files(zf: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    """A broker archive's manifest entries by path, empty when it has none."""
    try:
        info = zf.getinfo(_MANIFEST_NAME)
    except KeyError:
        return {}
    if info.file_size > _MAX_MANIFEST_BYTES:
        return {}
    try:
        manifest = json.loads(_read_member(zf, info))
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
        return {}
    files = manifest.get("files") if isinstance(manifest, dict) else None
    return {
        f["path"]: f
        for f in (files if isinstance(files, list) else [])
        if isinstance(f, dict) and isinstance(f.get("path"), str)
    }


_Staged = dict[str, tuple[bytes, dict[str, Any], zipfile.ZipInfo | None]]


@dataclass
class _ArchiveBudget:
    """Expanded-size and member-count budget for one archive build."""

    bytes_left: int = _MAX_EXPANDED_BYTES
    members_left: int = _MAX_MEMBERS

    def charge(self, size: int) -> None:
        self.bytes_left -= size
        self.members_left -= 1
        if self.bytes_left < 0 or self.members_left < 0:
            raise ValueError(
                "import archive exceeds the expanded-size or member-count limit"
            )


def _stage_zip(
    zf: zipfile.ZipFile,
    staged: _Staged,
    budget: _ArchiveBudget,
    *,
    skip_state: bool,
    place: Callable[[str, dict[str, Any] | None], tuple[str, dict[str, Any]]],
) -> None:
    """Stage each non-junk entry of `zf` at the path and manifest entry `place` picks.

    A later write at the same path replaces an earlier one, as a zip reader
    resolves duplicate entries.
    """
    files = _manifest_files(zf)
    for info in zf.infolist():
        name = _safe_name(info.filename)
        if info.is_dir() or name is None:
            continue
        entry = files.get(info.filename) or files.get(name)
        if skip_state and entry is not None and entry.get("kind") == "state":
            continue
        budget.charge(info.file_size)
        path, manifest_entry = place(name, entry)
        staged[path] = (_read_member(zf, info), manifest_entry, info)


def _write_member(
    member: ForeignMember, staged: _Staged, budget: _ArchiveBudget
) -> None:
    """Stage a foreign save archive's inner entries, or the member itself as one file."""

    def place(name: str, _entry: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
        path = f".import/{member.kind}/{name}"
        return path, {"path": path, "kind": member.kind, "origin": member.origin}

    # A state is one emulator file even when it is zip-shaped (a PCSX2 .p2s).
    inner = None
    if member.kind == "save":
        try:
            inner = zipfile.ZipFile(io.BytesIO(member.content))
        except zipfile.BadZipFile:
            pass
    if inner is None:
        budget.charge(len(member.content))
        path, entry = place(_safe_name(member.name) or "data", None)
        staged[path] = (member.content, entry, None)
        return
    with inner:
        # Another emulator's save archive also carries its exit state, which
        # a save pick must not bring along.
        _stage_zip(inner, staged, budget, skip_state=member.kind == "save", place=place)


def build_import_archive(
    rom_id: int,
    base: tuple[str, bytes] | None,
    members: list[ForeignMember],
) -> tuple[bytes, list[dict[str, Any]]]:
    """Build the single v2 zip `activate`'s `save.archive` wants: the base plus `.import/` members.

    Returns:
        The archive bytes, and the manifest's `files` list actually written.
    """
    ensure_zipfile_writable()
    staged: _Staged = {}
    budget = _ArchiveBudget()
    if base is not None:
        base_name, base_content = base
        try:
            base_zf = zipfile.ZipFile(io.BytesIO(base_content))
        except zipfile.BadZipFile:
            log.warning("base save archive is not a valid zip, %s", base_name)
        else:
            with base_zf:
                _stage_zip(
                    base_zf,
                    staged,
                    budget,
                    skip_state=any(m.kind == "state" for m in members),
                    place=lambda name, entry: (
                        name,
                        (
                            {**entry, "path": name}
                            if entry is not None
                            else {"path": name, "kind": "save"}
                        ),
                    ),
                )
    for member in members:
        _write_member(member, staged, budget)

    carried = [entry for _content, entry, _source in staged.values()]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, (content, _entry, source) in staged.items():
            zf.writestr(_utf8_zipinfo(path, source), content)
        zf.writestr(
            _MANIFEST_NAME,
            json.dumps(
                {
                    "version": 2,
                    "created_at": time.time(),
                    "import": {"source": "romm", "rom_id": rom_id},
                    "files": carried,
                }
            ),
        )
    return out.getvalue(), carried


async def _read_asset(file_path: str, file_name: str) -> bytes | None:
    try:
        return await fs_asset_handler.read_file(f"{file_path}/{file_name}")
    except FileNotFoundError:
        log.warning("import member missing on disk, %s", file_name)
        return None


class ImportHydration(NamedTuple):
    """What `hydrate_import_archive` actually got onto the container."""

    path: str | None = None
    state_imported: bool = False


async def hydrate_import_archive(
    user_id: int,
    rom: Rom,
    container: ResolvedContainer,
    *,
    save: Save | None,
    save_is_foreign: bool,
    state: State | None,
) -> ImportHydration:
    """Build this launch's one archive (native base plus `.import/` members) and upload it.

    Returns:
        The container path `activate`'s `save.archive` wants (None when
        there is nothing to send through the import path), and whether
        `state` specifically made it into the uploaded archive.
    """
    members: list[ForeignMember] = []
    if save is not None and save_is_foreign:
        archive = await saves.read_restorable_archive(save)
        if archive is not None:
            members.append(
                ForeignMember(
                    kind="save",
                    name=save.file_name,
                    content=archive[1],
                    origin=origin_of(save.emulator, save.origin_device_id),
                )
            )

    if state is not None:
        content = await _read_asset(state.file_path, state.file_name)
        if content is not None:
            members.append(
                ForeignMember(
                    kind="state",
                    name=states.container_state_filename(state.file_name),
                    content=content,
                    origin=origin_of(state.emulator, None),
                )
            )

    # Nothing foreign made it in, so the caller falls back to ordinary hydration.
    if not members:
        return ImportHydration()

    base: tuple[str, bytes] | None = None
    if not save_is_foreign:
        native = save or await asyncio.to_thread(
            saves.newest_restorable, user_id, rom.id, container.emulator
        )
        if native is not None:
            base = await saves.read_restorable_archive(native)

    archive_bytes, carried = await asyncio.to_thread(
        build_import_archive, rom.id, base, members
    )
    path = await asyncio.to_thread(
        webstation.upload_archive, container, f"rom-{rom.id}.zip", archive_bytes
    )
    # A member whose inner zip held only junk never lands in `carried`.
    state_included = path is not None and any(f.get("kind") == "state" for f in carried)
    return ImportHydration(path, state_included)
