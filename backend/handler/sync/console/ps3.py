"""Where a PS3 running webMAN MOD or multiMAN keeps its games and saves."""

from __future__ import annotations

import re
import struct
from collections.abc import Awaitable, Callable
from typing import Final

from redis.exceptions import RedisError

from handler.redis_handler import async_cache
from handler.sync.console.common import (
    CACHE_PREFIX,
    PARAM_SFO_MAX_BYTES,
    READ_ERRORS,
    ConsoleProfile,
    list_or_empty,
    normalize_title_id,
    read_sfo_field,
    sfo_field,
    title_id_of,
    title_ids_in,
)
from handler.sync.console.ftp import (
    AsyncConsoleFtp,
    ConsoleFtp,
    FtpEntry,
    FtpFileReader,
)
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import KNOWN_DEVICES
from utils.iso9660 import Iso9660
from utils.platform_slugs import UniversalPlatformSlug as UPS

# A save folder is a title id and at most 22 more characters (31 in all).
SAVE_FOLDER_PATTERN = re.compile(r"^[A-Z]{4}\d{5}[A-Z0-9_\-]{0,22}$")
_BRACKETED_TITLE_ID = re.compile(r"\[([A-Z]{4})-?(\d{5})\]", re.IGNORECASE)
_ISO_NAME = re.compile(r"\.iso(\.0)?$", re.IGNORECASE)

# Where webMAN and multiMAN look for games: the internal drive and USB ports.
_GAME_ROOTS = ("/dev_hdd0", *(f"/dev_usb{port:03d}" for port in range(8)))
# A game's identity never changes, so the key carries what would show a swap.
_TITLE_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
# A malformed image raises struct.error, or ValueError as Iso9660Error does.
_TITLE_READ_ERRORS: Final[tuple[type[Exception], ...]] = (
    ValueError,
    struct.error,
    *READ_ERRORS,
)


def _bracketed_title_id(name: str) -> str | None:
    match = _BRACKETED_TITLE_ID.search(name)
    return f"{match.group(1)}{match.group(2)}".upper() if match else None


def _sfo_title_id(data: bytes) -> str | None:
    title_id = sfo_field(data, "TITLE_ID")
    return title_id_of(normalize_title_id(title_id)) if title_id else None


class _TitleReader:
    def __init__(self, ftp: AsyncConsoleFtp, device_id: str) -> None:
        self.ftp = ftp
        self.device_id = device_id

    async def _cached(
        self,
        path: str,
        entry: FtpEntry,
        read: Callable[[], Awaitable[str | None]],
    ) -> str | None:
        stamp = entry.modified.isoformat() if entry.modified else ""
        key = f"{CACHE_PREFIX}:{self.device_id}:title:{path}:{entry.size}:{stamp}"
        try:
            cached = await async_cache.get(key)
        except RedisError:
            cached = None
        if isinstance(cached, bytes):
            cached = cached.decode()
        # "" records a game with no readable id, so it is not read every poll.
        if isinstance(cached, str):
            return cached or None

        title_id = await read()
        try:
            await async_cache.set(key, title_id or "", ex=_TITLE_CACHE_TTL_SECONDS)
        except RedisError as exc:
            log.debug(f"Could not cache the PS3 title id of {path}: {exc}")
        return title_id

    async def from_iso(self, path: str, entry: FtpEntry) -> str | None:
        if title_id := _bracketed_title_id(entry.display_name):
            return title_id

        def read_sfo(ftp: ConsoleFtp) -> bytes | None:
            return Iso9660(FtpFileReader(ftp, path)).read_file(
                "PS3_GAME/PARAM.SFO", PARAM_SFO_MAX_BYTES
            )

        async def read() -> str | None:
            try:
                data = await self.ftp.run(read_sfo)
            except _TITLE_READ_ERRORS as exc:
                log.debug(f"No PS3 title id in {hl(entry.display_name)}: {exc}")
                return None
            return _sfo_title_id(data) if data else None

        return await self._cached(path, entry, read)

    async def from_folder(self, path: str, entry: FtpEntry) -> str | None:
        if title_id := _bracketed_title_id(entry.display_name):
            return title_id

        async def read() -> str | None:
            try:
                data = await self.ftp.read(
                    f"{path}/PS3_GAME/PARAM.SFO", PARAM_SFO_MAX_BYTES
                )
            except _TITLE_READ_ERRORS as exc:
                log.debug(f"No PS3 title id in {hl(entry.display_name)}: {exc}")
                return None
            return _sfo_title_id(data)

        return await self._cached(path, entry, read)


async def discover_title_ids(ftp: AsyncConsoleFtp, device_id: str) -> set[str]:
    """Title ids of the games on the console: ISOs, game folders and installs."""
    reader = _TitleReader(ftp, device_id)
    title_ids: set[str] = set()

    for root in _GAME_ROOTS:
        folders = {
            entry.name.upper(): entry.name
            for entry in await list_or_empty(ftp, root)
            if entry.is_dir
        }

        # Installed games, game data and updates, each in a folder named by id.
        if "GAME" in folders:
            title_ids |= await title_ids_in(ftp, f"{root}/{folders['GAME']}")

        if "PS3ISO" in folders:
            iso_dir = f"{root}/{folders['PS3ISO']}"
            for entry in await list_or_empty(ftp, iso_dir):
                if not entry.is_dir and _ISO_NAME.search(entry.name):
                    path = f"{iso_dir}/{entry.name}"
                    if title_id := await reader.from_iso(path, entry):
                        title_ids.add(title_id)

        if "GAMES" in folders:
            games_dir = f"{root}/{folders['GAMES']}"
            for entry in await list_or_empty(ftp, games_dir):
                if entry.is_dir:
                    path = f"{games_dir}/{entry.name}"
                    if title_id := await reader.from_folder(path, entry):
                        title_ids.add(title_id)

    return title_ids


async def _save_title(
    ftp: AsyncConsoleFtp, folder_path: str, files: list[FtpEntry]
) -> str | None:
    if not any(f.name == "PARAM.SFO" for f in files):
        return None
    return await read_sfo_field(ftp, f"{folder_path}/PARAM.SFO", "TITLE")


PS3 = ConsoleProfile(
    device_type=KNOWN_DEVICES["ps3"],
    platform_slug=UPS.PS3,
    title="PlayStation 3",
    default_ftp_port=21,
    home_root="/dev_hdd0/home",
    user_pattern=re.compile(r"^\d{8}$"),
    user_name_file="localusername",
    save_folder_pattern=SAVE_FOLDER_PATTERN,
    folder_max_bytes=256 * 1024 * 1024,
    is_save=lambda names: "PARAM.SFO" in names,
    discover_title_ids=discover_title_ids,
    save_title=_save_title,
)
