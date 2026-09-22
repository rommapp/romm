"""Folding a foreign-emulator save or state pick into the one archive a
launch's `activate` call sends.

RomM never interprets a foreign asset's bytes; it only tags, wraps, and
carries them under a `.import/<kind>/<name>` member for the broker's own
declared-import contract to place. See docs/superpowers/specs/2026-09-21-
declared-save-import-romm-design.md for the wire format this builds toward.
"""

import asyncio
import io
import json
import time
import zipfile
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

# A base or foreign archive's nested zip entries are trusted only for their
# own central-directory metadata (`info.file_size`) until charged here, never
# for their compressed size: a small, highly compressible upload could
# otherwise expand far past what it looked like on disk. Reuses the same
# ceiling as any other stored save archive rather than inventing a second one.
_MAX_EXPANDED_BYTES = broker.SAVE_FILE_MAX_BYTES
_MAX_MEMBERS = 2000


@dataclass(frozen=True)
class ForeignMember:
    """One foreign pick's bytes, waiting to be folded into the launch's
    single `.import/` archive."""

    kind: Literal["save", "state"]
    name: str
    content: bytes
    origin: str


def origin_of(emulator: str | None, origin_device_id: str | None) -> str:
    """Where a picked save/state was captured, advisory-only per the
    broker's v2 manifest: "hardware" when a device tagged it, "unknown" for
    an untagged manual upload, "standalone" when its `emulator` names one of
    the streaming subsystem's own containers, else "emulatorjs" (EmulatorJS
    writes its active core's name into the same field)."""
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


def _utf8_zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    info.flag_bits |= 0x800  # UTF-8 filename flag
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _read_base_manifest(base_zf: zipfile.ZipFile) -> dict[str, Any] | None:
    if _MANIFEST_NAME not in base_zf.namelist():
        return None
    try:
        manifest = json.loads(base_zf.read(_MANIFEST_NAME))
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
        return None
    return manifest if isinstance(manifest, dict) else None


_Staged = dict[str, tuple[bytes, dict[str, Any]]]


@dataclass
class _ArchiveBudget:
    """Cumulative expanded-size and member-count budget for one archive
    build, charged from each entry's own metadata before it is read."""

    bytes_left: int = _MAX_EXPANDED_BYTES
    members_left: int = _MAX_MEMBERS

    def charge(self, size: int) -> None:
        self.bytes_left -= size
        self.members_left -= 1
        if self.bytes_left < 0 or self.members_left < 0:
            raise ValueError(
                "import archive exceeds the expanded-size or member-count limit"
            )


def _write_member(
    member: ForeignMember, staged: _Staged, budget: _ArchiveBudget
) -> None:
    """Stage one foreign member's own inner entries (or itself, when not a
    zip) by archive path. A later write at the same path replaces an
    earlier one rather than duplicating it, matching how a zip reader
    resolves duplicate entries."""
    if zipfile.is_zipfile(io.BytesIO(member.content)):
        with zipfile.ZipFile(io.BytesIO(member.content)) as inner:
            for info in inner.infolist():
                if info.is_dir():
                    continue
                name = _safe_name(info.filename)
                if name is None:
                    continue
                budget.charge(info.file_size)
                path = f".import/{member.kind}/{name}"
                staged[path] = (
                    inner.read(info.filename),
                    {"path": path, "kind": member.kind, "origin": member.origin},
                )
        return
    budget.charge(len(member.content))
    name = _safe_name(member.name) or "data"
    path = f".import/{member.kind}/{name}"
    staged[path] = (
        member.content,
        {"path": path, "kind": member.kind, "origin": member.origin},
    )


def build_import_archive(
    rom_id: int,
    base: tuple[str, bytes] | None,
    members: list[ForeignMember],
) -> tuple[bytes, list[dict[str, Any]]]:
    """Build the single zip `activate`'s `save.archive` wants.

    Carries over the base archive's own members verbatim (its old
    `.broker-manifest.json` is dropped and rewritten as v2), except its v1
    state member, which is stripped whenever a foreign state is among
    `members` since the import replaces it. Adds one `.import/<kind>/<name>`
    member per foreign member (its own inner members, when its content is
    itself a zip). Drops dotfiles and `__MACOSX` entries and forces UTF-8
    names on every member copied in, base or foreign. A path collision
    (base vs. a foreign member, or between two foreign members' own inner
    zips) keeps only the last write.

    Returns:
        The archive bytes, and the manifest's `files` list actually written.
    """
    ensure_zipfile_writable()
    strip_state = any(m.kind == "state" for m in members)
    staged: _Staged = {}
    budget = _ArchiveBudget()
    if base is not None:
        base_name, base_content = base
        try:
            base_zf_handle = zipfile.ZipFile(io.BytesIO(base_content))
        except zipfile.BadZipFile:
            log.warning("base save archive is not a valid zip, %s", base_name)
            base_zf_handle = None
        if base_zf_handle is not None:
            with base_zf_handle as base_zf:
                base_manifest = _read_base_manifest(base_zf)
                base_files = {
                    f["path"]: f
                    for f in (base_manifest or {}).get("files", [])
                    if isinstance(f, dict) and isinstance(f.get("path"), str)
                }
                for info in base_zf.infolist():
                    if info.is_dir() or info.filename == _MANIFEST_NAME:
                        continue
                    name = _safe_name(info.filename)
                    if name is None:
                        continue
                    entry = base_files.get(info.filename) or base_files.get(name)
                    if (
                        strip_state
                        and entry is not None
                        and entry.get("kind") == "state"
                    ):
                        continue
                    budget.charge(info.file_size)
                    staged[name] = (
                        base_zf.read(info.filename),
                        entry if entry is not None else {"path": name, "kind": "save"},
                    )
    for member in members:
        _write_member(member, staged, budget)

    carried = [entry for _content, entry in staged.values()]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, (content, _entry) in staged.items():
            zf.writestr(_utf8_zipinfo(path), content)
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

    path: str | None
    state_imported: bool


async def hydrate_import_archive(
    user_id: int,
    rom: Rom,
    container: ResolvedContainer,
    *,
    save: Save | None,
    save_is_foreign: bool,
    state: State | None,
) -> ImportHydration:
    """Build this launch's one archive (native base plus any foreign
    `.import/` members) and upload it.

    `state` rides here whenever the container takes no separate state push:
    a foreign pick always, and a native one on an archive-resume container
    (DuckStation, RPCS3), since a push after activate would be refused.

    Returns:
        The container path `activate`'s `save.archive` wants (None when
        there is nothing to send through the import path), and whether
        `state` specifically made it into the uploaded archive.
    """
    members: list[ForeignMember] = []
    base: tuple[str, bytes] | None = None

    if save is not None and save_is_foreign:
        archive = await saves.read_restorable_archive(save)
        if archive is not None:
            _file_name, save_content = archive
            members.append(
                ForeignMember(
                    kind="save",
                    name=save.file_name,
                    content=save_content,
                    origin=origin_of(save.emulator, save.origin_device_id),
                )
            )
    elif save is not None:
        base = await saves.read_restorable_archive(save)
    else:
        newest = saves.newest_restorable(user_id, rom.id, container.emulator)
        if newest is not None:
            base = await saves.read_restorable_archive(newest)

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

    if not members:
        # No foreign material made it in (nothing was foreign, or reading it
        # failed): there is nothing to import. Let the caller fall through
        # to ordinary hydration for any native save, rather than uploading a
        # v2 archive whose `.import/` section is empty.
        return ImportHydration(None, False)

    archive_bytes, carried = await asyncio.to_thread(
        build_import_archive, rom.id, base, members
    )
    path = await asyncio.to_thread(
        webstation.upload_archive, container, f"rom-{rom.id}.zip", archive_bytes
    )
    # A member whose own inner zip filtered out to nothing (junk entries
    # only) never lands in `carried`, so this reflects what actually made it
    # into the archive rather than merely what was attempted.
    state_included = path is not None and any(f.get("kind") == "state" for f in carried)
    return ImportHydration(path, state_included)
