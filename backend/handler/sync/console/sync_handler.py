"""Two-way save sync with a console over FTP, one slot per ``savedata/`` folder."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from tempfile import SpooledTemporaryFile
from typing import IO, Any

from pydantic import ValidationError
from redis.exceptions import RedisError

from handler.asset_store import prune_save_slot, reserve_version_name
from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_device_save_sync_handler,
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_sync_session_handler,
    db_user_handler,
)
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache, high_prio_queue
from handler.sync.comparison import compare_save_state
from handler.sync.console.common import (
    CACHE_PREFIX,
    ConsoleProfile,
    ConsoleSyncConfig,
    is_lan_address,
    normalize_title_id,
    title_id_of,
)
from handler.sync.console.ftp import FTP_ERRORS, AsyncConsoleFtp, FtpEntry
from handler.sync.console.profiles import profile_of
from handler.sync.retroarch.psp import normalize_title
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, SaveLineage
from models.device import Device
from models.device_save_sync import DeviceSaveSync
from models.platform import Platform
from models.rom import Rom
from models.sync_session import SyncSession, SyncSessionStatus
from models.user import User
from tasks.registry import SYNC_PUSH_PULL_SPEC
from utils.datetime import to_utc
from utils.zip_cache import ensure_zipfile_writable

# A save folder holds a handful of files; anything past this is not one.
_FOLDER_MAX_FILES = 128
_MEMBER_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
# A version past this spills from memory to a temporary file.
_SPOOL_MAX_BYTES = 16 * 1024 * 1024

# Neither matches a save folder pattern, so no sync takes them for a save.
_STAGING_SUFFIX = ".ROMMNEW"
_RETIRED_SUFFIX = ".ROMMOLD"

_FINGERPRINT_TTL_SECONDS = 30 * 24 * 60 * 60
# A first sync can move gigabytes over a console's slow FTP server, so the job
# gets as long as the lock, which must outlive it.
_LOCK_TTL_SECONDS = 60 * 60


class ConsoleSaveInvalid(Exception):
    """A save folder, or a stored version of one, is not a save of its console."""


@dataclass
class ConsoleSyncCounts:
    pulled: int = 0
    pushed: int = 0
    unchanged: int = 0
    conflicts: int = 0
    unmatched: int = 0
    failed: int = 0
    unmatched_folders: list[str] = field(default_factory=list)

    @property
    def completed(self) -> int:
        return self.pulled + self.pushed


def _fingerprint(files: list[FtpEntry]) -> str:
    """What changes whenever the console rewrites a file of the folder."""
    listing = sorted(
        (f.name, f.size, f.modified.isoformat() if f.modified else "") for f in files
    )
    return hashlib.sha256(json.dumps(listing).encode()).hexdigest()


def _is_member_name(name: str) -> bool:
    return bool(_MEMBER_NAME.match(name)) and name not in (".", "..")


class _HashingSink:
    """A zip entry being written, and the md5 of what went into it."""

    def __init__(self, entry: IO[bytes]) -> None:
        self._entry = entry
        self.md5 = hashlib.md5(usedforsecurity=False)

    def write(self, chunk: bytes) -> None:
        self.md5.update(chunk)
        self._entry.write(chunk)


@dataclass
class _Download:
    """A folder zipped as a stored version, and that version's content hash."""

    archive: SpooledTemporaryFile[bytes]
    content_hash: str

    @property
    def size(self) -> int:
        return self.archive.seek(0, 2)


def _stored_members(
    path: str, folder: str, profile: ConsoleProfile
) -> list[zipfile.ZipInfo]:
    """The entries of a stored version, checked to be one flat save folder.

    Raises:
        ConsoleSaveInvalid: The zip holds anything else, or exceeds the folder
            limits.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
    except zipfile.BadZipFile as exc:
        raise ConsoleSaveInvalid(f"{path} is not a zip") from exc
    if len(infos) > _FOLDER_MAX_FILES or (
        sum(info.file_size for info in infos) > profile.folder_max_bytes
    ):
        raise ConsoleSaveInvalid(f"{path} exceeds the save folder limits")
    names = set()
    for info in infos:
        parent, _, name = info.filename.rpartition("/")
        if parent not in ("", folder) or not _is_member_name(name):
            raise ConsoleSaveInvalid(f"{path} holds {info.filename}")
        names.add(name)
    if not profile.is_save(names):
        raise ConsoleSaveInvalid(f"{path} is not a {profile.title} save")
    return infos


class _RomIndex:
    """The console's ROMs, by title id and by the title a save names."""

    def __init__(self, roms: list[Rom]) -> None:
        self._by_title_id: dict[str, Rom] = {}
        self._by_title: dict[str, Rom] = {}
        for rom in roms:
            if rom.title_id:
                self._by_title_id.setdefault(normalize_title_id(rom.title_id), rom)
            for name in (rom.name, rom.fs_name_no_tags):
                if name and (key := normalize_title(name)):
                    self._by_title.setdefault(key, rom)

    def by_title_id(self, title_id: str | None) -> Rom | None:
        return self._by_title_id.get(title_id) if title_id else None

    def by_title(self, title: str | None) -> Rom | None:
        return self._by_title.get(normalize_title(title)) if title else None


class _ConsoleSync:
    def __init__(
        self,
        device: Device,
        profile: ConsoleProfile,
        ftp: AsyncConsoleFtp,
        config: ConsoleSyncConfig,
        platform: Platform,
        session_id: int,
    ) -> None:
        self.device = device
        self.profile = profile
        self.ftp = ftp
        self.config = config
        self.platform = platform
        self.session_id = session_id
        self.savedata = profile.savedata_path(config.user_id)
        self.emulator = profile.kind
        self.counts = ConsoleSyncCounts()
        self.heads: dict[tuple[int, str], Save] = {}
        self.version_ids: dict[tuple[int, str], list[int]] = {}

    async def run(self) -> ConsoleSyncCounts:
        from endpoints.sockets.sync import emit_sync_progress

        await self._recover_interrupted_pushes()
        folders = [
            entry
            for entry in await self.ftp.list(self.savedata)
            if entry.is_dir and self.profile.save_folder_pattern.match(entry.name)
        ]
        on_console = await self.profile.discover_title_ids(self.ftp, self.device.id)
        on_console |= {t for f in folders if (t := title_id_of(f.name))}

        roms = _RomIndex(
            list(db_rom_handler.get_roms_scalar(platform_ids=[self.platform.id]))
        )
        self._load_heads()

        db_sync_session_handler.update_session(
            session_id=self.session_id,
            data={
                "status": SyncSessionStatus.IN_PROGRESS,
                "operations_planned": len(folders),
            },
        )

        for done, folder in enumerate(folders, start=1):
            try:
                await self._sync_folder(folder, roms)
            except Exception:
                log.error(
                    f"Console sync: failed to sync {hl(folder.name)} "
                    f"on device {self.device.id}",
                    exc_info=True,
                )
                self.counts.failed += 1
            await emit_sync_progress(
                user_id=self.device.user_id,
                device_id=self.device.id,
                session_id=self.session_id,
                operations_completed=done,
                operations_planned=len(folders),
                current_file=folder.name,
            )

        await self._push_missing({f.name for f in folders}, on_console)
        return self.counts

    @cached_property
    def _user(self) -> User:
        user = db_user_handler.get_user(self.device.user_id)
        if user is None:
            raise LookupError(f"Device {self.device.id} has no user")
        return user

    def _load_heads(self) -> None:
        """The newest version of each slot of this console's saves, by (rom id, slot)."""
        saves = db_save_handler.get_saves(
            user_id=self.device.user_id,
            platform_id=self.platform.id,
            slot_not_null=True,
            order_by="updated_at",
        )
        for save in saves:
            if save.emulator == self.emulator and save.slot:
                self.heads.setdefault((save.rom_id, save.slot), save)
                self.version_ids.setdefault((save.rom_id, save.slot), []).append(
                    save.id
                )

    def _baseline(self, key: tuple[int, str]) -> DeviceSaveSync | None:
        """The latest sync of any version, so a newer one reads as a server change."""
        syncs = db_device_save_sync_handler.get_syncs_for_device_and_saves(
            device_id=self.device.id, save_ids=self.version_ids.get(key, [])
        )
        return max(syncs, key=lambda s: to_utc(s.last_synced_at), default=None)

    async def _recover_interrupted_pushes(self) -> None:
        """Finish or undo a push a dropped connection left half done."""
        entries = {e.name for e in await self.ftp.list(self.savedata) if e.is_dir}
        for name in entries:
            path = f"{self.savedata}/{name}"
            if name.endswith(_RETIRED_SUFFIX):
                original = name.removesuffix(_RETIRED_SUFFIX)
                if original in entries:
                    await self.ftp.remove_tree(path)
                else:
                    await self.ftp.rename(path, f"{self.savedata}/{original}")
                log.warning(
                    f"Console sync: recovered an interrupted push of {original}"
                )
            elif name.endswith(_STAGING_SUFFIX):
                await self.ftp.remove_tree(path)

    def _fingerprint_key(self, folder: str) -> str:
        return f"{CACHE_PREFIX}:{self.device.id}:folder:{folder}"

    async def _known_hash(self, folder: str, fingerprint: str) -> str | None:
        """The folder's content hash when its files are as last seen."""
        try:
            raw = await async_cache.get(self._fingerprint_key(folder))
        except RedisError:
            return None
        if not raw:
            return None
        known = json.loads(raw)
        return known["hash"] if known.get("fingerprint") == fingerprint else None

    async def _remember_hash(
        self, folder: str, files: list[FtpEntry], content_hash: str
    ) -> None:
        value = json.dumps({"fingerprint": _fingerprint(files), "hash": content_hash})
        try:
            await async_cache.set(
                self._fingerprint_key(folder), value, ex=_FINGERPRINT_TTL_SECONDS
            )
        except RedisError as exc:
            log.debug(f"Console sync: could not remember {folder}'s hash: {exc}")

    async def _list_files(self, folder: str) -> list[FtpEntry]:
        files = await self.ftp.list(f"{self.savedata}/{folder}")
        if any(f.is_dir for f in files):
            raise ConsoleSaveInvalid(f"{folder} holds a subfolder")
        if len(files) > _FOLDER_MAX_FILES or sum(f.size for f in files) > (
            self.profile.folder_max_bytes
        ):
            raise ConsoleSaveInvalid(f"{folder} exceeds the save folder limits")
        return files

    async def _download(self, folder: str, files: list[FtpEntry]) -> _Download | None:
        """The folder zipped, or None when the console rewrote it meanwhile."""
        # `zipfile_inflate64` is imported elsewhere for ROM archive reading, and
        # breaks writing until this runs.
        ensure_zipfile_writable()
        archive: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
            max_size=_SPOOL_MAX_BYTES
        )
        try:
            budget = self.profile.folder_max_bytes
            # Hashed as `hash_zip_contents` would, without its cap on entry size.
            entry_hashes = []
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in sorted(files, key=lambda f: f.name):
                    if not _is_member_name(file.name):
                        raise ConsoleSaveInvalid(f"{folder} holds {file.display_name}")
                    member = f"{folder}/{file.name}"
                    with zf.open(member, "w", force_zip64=True) as entry:
                        sink = _HashingSink(entry)
                        budget -= await self.ftp.download(
                            f"{self.savedata}/{member}", sink.write, budget
                        )
                    entry_hashes.append(f"{member}:{sink.md5.hexdigest()}")
            # Files read across a save are from two moments, so a change voids it.
            if await self._fingerprint_now(folder) != _fingerprint(files):
                log.info(
                    f"Console sync: {hl(folder)} changed while read, left for next sync"
                )
                archive.close()
                return None
        except BaseException:
            archive.close()
            raise
        content_hash = hashlib.md5(
            "\n".join(entry_hashes).encode(), usedforsecurity=False
        ).hexdigest()
        return _Download(archive=archive, content_hash=content_hash)

    async def _fingerprint_now(self, folder: str) -> str | None:
        """The folder's fingerprint as it stands, or None when it is gone."""
        if not await self.ftp.exists(f"{self.savedata}/{folder}"):
            return None
        return _fingerprint(await self._list_files(folder))

    async def _sync_folder(self, folder: FtpEntry, roms: _RomIndex) -> None:
        name = folder.name
        files = await self._list_files(name)
        if not files:
            return

        rom = roms.by_title_id(title_id_of(name)) or roms.by_title(
            await self.profile.save_title(self.ftp, f"{self.savedata}/{name}", files)
        )
        if rom is None:
            self.counts.unmatched += 1
            self.counts.unmatched_folders.append(name)
            log.debug(f"Console sync: no ROM in the library matches {hl(name)}")
            return

        fingerprint = _fingerprint(files)
        download: _Download | None = None
        try:
            console_hash = await self._known_hash(name, fingerprint)
            if console_hash is None:
                download = await self._download(name, files)
                if download is None:
                    return
                console_hash = download.content_hash
                await self._remember_hash(name, files, console_hash)
            await self._reconcile(rom, name, files, fingerprint, console_hash, download)
        finally:
            if download:
                download.archive.close()

    async def _reconcile(
        self,
        rom: Rom,
        name: str,
        files: list[FtpEntry],
        fingerprint: str,
        console_hash: str,
        download: _Download | None,
    ) -> None:
        head = self.heads.get((rom.id, name))
        if head is None:
            await self._pull(rom, name, files, download, console_hash)
            return

        device_sync = self._baseline((rom.id, name))
        if device_sync and device_sync.is_untracked:
            self.counts.unchanged += 1
            return
        changed_on_console = bool(
            device_sync
            and device_sync.last_sync_hash
            and device_sync.last_sync_hash != console_hash
        )
        written_at = max(
            (f.modified for f in files if f.modified),
            default=datetime.now(timezone.utc),
        )
        result = compare_save_state(
            client_hash=console_hash,
            # A hash past the baseline was written after that sync, whatever
            # the console's clock (often local time sent as UTC) says.
            client_updated_at=(
                datetime.now(timezone.utc) if changed_on_console else written_at
            ),
            server_hash=head.content_hash,
            server_updated_at=head.updated_at,
            device_last_synced_at=device_sync.last_synced_at if device_sync else None,
            device_last_sync_hash=device_sync.last_sync_hash if device_sync else None,
            device_last_sync_server_hash=(
                device_sync.last_sync_server_hash if device_sync else None
            ),
            removed_at=(
                db_deleted_asset_handler.removal_times(
                    self.device.user_id, rom.id, name
                )
                if console_hash != head.content_hash
                else None
            ),
        )

        if result.action == "no_op":
            # Only identical content is a baseline; recording a timestamp-only
            # no-op would hide the difference from the next comparison.
            if console_hash == head.content_hash:
                db_device_save_sync_handler.upsert_sync(
                    device_id=self.device.id,
                    save_id=head.id,
                    last_sync_hash=console_hash,
                    last_sync_server_hash=console_hash,
                )
            self.counts.unchanged += 1
        elif result.action == "upload":
            await self._pull(rom, name, files, download, console_hash)
        elif result.action == "download":
            if await self._push(head, name, expected=fingerprint):
                self.counts.pushed += 1
            else:
                self.counts.unchanged += 1
        elif result.action == "conflict":
            await self._report_conflict(rom, name, result.reason)

    async def _pull(
        self,
        rom: Rom,
        folder: str,
        files: list[FtpEntry],
        download: _Download | None,
        content_hash: str,
    ) -> None:
        """File the console's folder as the slot's newest version."""
        user = self._user
        existing = db_save_handler.get_save_by_content_hash(
            user_id=user.id, rom_id=rom.id, content_hash=content_hash, slot=folder
        )
        if existing:
            save = db_save_handler.promote_to_slot_head(existing)
        else:
            owned = download is None
            if download is None:
                download = await self._download(folder, files)
                if download is None:
                    return
            try:
                save = await self._store(rom, folder, download)
            finally:
                if owned:
                    download.archive.close()

        await prune_save_slot(
            user.id,
            rom.id,
            folder,
            self.config.keep_versions,
            lineage=SaveLineage.of(self.emulator, save.file_name),
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=self.device.id,
            save_id=save.id,
            last_sync_hash=content_hash,
            last_sync_server_hash=content_hash,
        )
        self.heads[(rom.id, folder)] = save
        self.version_ids.setdefault((rom.id, folder), []).append(save.id)
        self.counts.pulled += 1

    async def _store(self, rom: Rom, folder: str, download: _Download) -> Save:
        user = self._user
        saves_path = fs_asset_handler.build_saves_file_path(
            user=user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=self.emulator,
        )
        file_name = await reserve_version_name(
            user.id, rom.id, saves_path, f"{folder}.zip"
        )
        await fs_asset_handler.write_file(
            file=download.archive, path=saves_path, filename=file_name
        )
        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=user.id,
                file_name=file_name,
                file_path=saves_path,
                file_size_bytes=download.size,
                content_hash=download.content_hash,
                emulator=self.emulator,
                slot=folder,
                origin_device_id=self.device.id,
            )
        )
        log.info(
            f"Console sync: pulled {hl(folder)} for {hl(str(rom.name))} "
            f"from device {self.device.id}"
        )
        return save

    async def _push(self, save: Save, folder: str, expected: str | None) -> bool:
        """Write a stored version over the folder last seen as `expected`.

        Returns:
            False when the version may not go to this console, or the console
            wrote the folder since it was compared.
        """
        # Saves are signed or sealed for one console and user, so a save from
        # anywhere else would read as corrupted on this one.
        if save.origin_device_id != self.device.id:
            log.info(
                f"Console sync: not pushing {hl(folder)} to device {self.device.id}, "
                "its newest version comes from another device"
            )
            return False

        path = str(fs_asset_handler.validate_path(save.full_path))
        infos = _stored_members(path, folder, self.profile)
        target = f"{self.savedata}/{folder}"
        staging = f"{target}{_STAGING_SUFFIX}"
        retired = f"{target}{_RETIRED_SUFFIX}"

        # Written beside the save and swapped in, so a dropped connection never
        # leaves the console a half-written save.
        await self.ftp.mkdir(staging)
        with zipfile.ZipFile(path) as zf:
            for info in infos:
                name = info.filename.rpartition("/")[2]
                with zf.open(info) as member:
                    await self.ftp.upload(f"{staging}/{name}", member)
        current = await self._fingerprint_now(folder)
        if current != expected:
            await self.ftp.remove_tree(staging)
            log.info(
                f"Console sync: {hl(folder)} changed while pushing, left for next sync"
            )
            return False
        replacing = current is not None
        if replacing:
            await self.ftp.rename(target, retired)
        await self.ftp.rename(staging, target)
        if replacing:
            await self.ftp.remove_tree(retired)

        if save.content_hash:
            await self._remember_hash(
                folder, await self._list_files(folder), save.content_hash
            )
        db_device_save_sync_handler.upsert_sync(
            device_id=self.device.id,
            save_id=save.id,
            last_sync_hash=save.content_hash,
            last_sync_server_hash=save.content_hash,
        )
        log.info(f"Console sync: pushed {hl(folder)} to device {self.device.id}")
        return True

    async def _push_missing(self, on_console: set[str], titles: set[str]) -> None:
        """Push slots the console lacks, for the games it holds."""
        for key, head in self.heads.items():
            folder = key[1]
            if folder in on_console or not self.profile.save_folder_pattern.match(
                folder
            ):
                continue
            if title_id_of(folder) not in titles:
                continue
            # A slot the console ever synced and lacks now was deleted there.
            if self._baseline(key):
                continue
            try:
                if await self._push(head, folder, expected=None):
                    self.counts.pushed += 1
            except Exception:
                log.error(
                    f"Console sync: failed to push {hl(folder)} "
                    f"to device {self.device.id}",
                    exc_info=True,
                )
                self.counts.failed += 1

    async def _report_conflict(self, rom: Rom, folder: str, reason: str) -> None:
        from endpoints.sockets.sync import emit_sync_conflict

        log.warning(
            f"Console sync: conflict for {hl(folder)} "
            f"on device {self.device.id}: {reason}"
        )
        await emit_sync_conflict(
            user_id=self.device.user_id,
            device_id=self.device.id,
            session_id=self.session_id,
            file_name=folder,
            rom_id=rom.id,
            rom_name=rom.name or rom.fs_name,
            reason=reason,
        )
        self.counts.conflicts += 1


def _lock_key(address: str, config: ConsoleSyncConfig) -> str:
    """One key per save directory, however many devices point at it."""
    return f"{CACHE_PREFIX}:lock:{address}:{config.ftp_port}:{config.user_id}"


def enqueue_console_sync(device: Device) -> SyncSession:
    """Queue a sync of the console under a new session, which it returns."""
    sync_session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=device.user_id
    )
    high_prio_queue.enqueue(
        "tasks.sync_push_pull_task.run_push_pull_sync",
        device_id=device.id,
        session_id=sync_session.id,
        force=True,
        job_timeout=_LOCK_TTL_SECONDS,
        meta=SYNC_PUSH_PULL_SPEC.job_meta("sync_push_pull"),
    )
    return sync_session


async def sync_console_device(
    device: Device, session_id: int | None = None
) -> dict[str, Any]:
    """Sync one console's saves both ways, under the device's sync session."""
    from endpoints.sockets.sync import (
        emit_sync_completed,
        emit_sync_error,
        emit_sync_started,
    )

    sync_session = (
        db_sync_session_handler.get_session(
            session_id=session_id, user_id=device.user_id
        )
        if session_id
        else None
    ) or db_sync_session_handler.create_session(
        device_id=device.id, user_id=device.user_id
    )

    async def fail(message: str, status: str) -> dict[str, Any]:
        db_sync_session_handler.fail_session(
            session_id=sync_session.id, error_message=message
        )
        await emit_sync_error(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            error_message=message,
        )
        return {"device_id": device.id, "status": status, "error": message}

    profile = profile_of(device)
    if profile is None:
        return await fail(f"{device.client} is not a console RomM syncs", "error")
    if not device.ip_address or not is_lan_address(device.ip_address):
        return await fail("No address on the local network configured", "error")
    try:
        config = ConsoleSyncConfig.of(profile, device.sync_config)
    except ValidationError as exc:
        return await fail(f"Invalid sync settings: {exc}", "error")
    platform = db_platform_handler.get_platform_by_slug(profile.platform_slug)
    if not platform:
        return await fail(f"The library has no {profile.title} platform", "error")
    lock_key = _lock_key(device.ip_address, config)
    if not await async_cache.set(
        lock_key, sync_session.id, nx=True, ex=_LOCK_TTL_SECONDS
    ):
        return await fail("Another sync of this console is running", "busy")

    try:
        await emit_sync_started(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            sync_mode="push_pull",
        )
        try:
            ftp = await AsyncConsoleFtp.connect(device.ip_address, config.ftp_port)
        except FTP_ERRORS as exc:
            log.warning(f"Console sync: could not connect to device {device.id}: {exc}")
            return await fail(f"Could not connect: {exc}", "connection_failed")

        try:
            counts = await _ConsoleSync(
                device, profile, ftp, config, platform, sync_session.id
            ).run()
        except Exception as exc:
            log.error(f"Console sync failed for device {device.id}", exc_info=True)
            return await fail(str(exc), "failed")
        finally:
            await ftp.close()
    finally:
        await async_cache.delete(lock_key)

    db_sync_session_handler.complete_session(
        session_id=sync_session.id,
        operations_completed=counts.completed,
        operations_failed=counts.failed,
    )
    db_device_handler.update_last_seen(device_id=device.id, user_id=device.user_id)
    await emit_sync_completed(
        user_id=device.user_id,
        device_id=device.id,
        session_id=sync_session.id,
        operations_completed=counts.completed,
        operations_failed=counts.failed,
    )
    if counts.unmatched_folders:
        log.info(
            f"Console sync: {counts.unmatched} save folder(s) on device {device.id} "
            f"match no ROM: {', '.join(counts.unmatched_folders)}"
        )
    log.info(
        f"Console sync for device {device.id}: {counts.pulled} pulled, "
        f"{counts.pushed} pushed, {counts.unchanged} unchanged, "
        f"{counts.conflicts} conflicts, {counts.failed} failed"
    )
    return {
        "device_id": device.id,
        "status": "completed",
        "pulled": counts.pulled,
        "pushed": counts.pushed,
        "unchanged": counts.unchanged,
        "conflicts": counts.conflicts,
        "unmatched": counts.unmatched,
        "failed": counts.failed,
    }
