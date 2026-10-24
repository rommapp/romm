"""A PS3's sync settings, and which games it holds."""

from __future__ import annotations

# The PS3 serves its files over plain FTP only, and only on the LAN.
import ftplib  # nosec B402
import re
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Final

from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from config import MAX_AUTOCLEANUP_LIMIT
from handler.redis_handler import async_cache
from handler.sync.ps3.ftp import (
    FTP_ERRORS,
    AsyncPS3Ftp,
    FtpEntry,
    FtpFileReader,
    FtpFileTooLarge,
    PS3Ftp,
    probe,
)
from handler.sync.retroarch.psp import parse_sfo
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import KNOWN_DEVICES, Device
from utils.iso9660 import Iso9660

PS3_DEVICE_TYPE = KNOWN_DEVICES["ps3"]

TITLE_ID_PATTERN = re.compile(r"^[A-Z]{4}\d{5}")
# A save folder is a title id and at most 22 more characters (31 in all).
SAVE_FOLDER_PATTERN = re.compile(r"^[A-Z]{4}\d{5}[A-Z0-9_\-]{0,22}$")
_BRACKETED_TITLE_ID = re.compile(r"\[([A-Z]{4})-?(\d{5})\]", re.IGNORECASE)
_ISO_NAME = re.compile(r"\.iso(\.0)?$", re.IGNORECASE)

# Where webMAN and multiMAN look for games: the internal drive and USB ports.
_GAME_ROOTS = ("/dev_hdd0", *(f"/dev_usb{port:03d}" for port in range(8)))
_PARAM_SFO_MAX_BYTES = 64 * 1024
# A game's identity never changes, so the key carries what would show a swap.
_TITLE_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_READ_ERRORS: Final[tuple[type[Exception], ...]] = (FtpFileTooLarge, *FTP_ERRORS)
# A malformed image raises struct.error, or ValueError as Iso9660Error does.
_TITLE_READ_ERRORS: Final[tuple[type[Exception], ...]] = (
    ValueError,
    struct.error,
    *_READ_ERRORS,
)


FtpPort = Annotated[int, Field(ge=1, le=65535)]
PS3User = Annotated[
    str,
    Field(
        pattern=r"^\d{8}$", description="The PS3 user profile whose saves are synced."
    ),
]
PollIntervalMinutes = Annotated[int, Field(ge=1, le=24 * 60)]
KeepVersions = Annotated[int, Field(ge=1, le=MAX_AUTOCLEANUP_LIMIT)]


class PS3SyncConfig(BaseModel):
    """What `Device.sync_config` holds for a PS3; its address is `Device.ip_address`."""

    ftp_port: FtpPort = 21
    ps3_user: PS3User = "00000001"
    poll_interval_minutes: PollIntervalMinutes = 15
    keep_versions: KeepVersions = 10

    @classmethod
    def of(cls, sync_config: dict[str, Any] | None) -> PS3SyncConfig:
        return cls.model_validate(sync_config or {})

    @property
    def savedata_path(self) -> str:
        return f"/dev_hdd0/home/{self.ps3_user}/savedata"


def is_ps3(device: Device) -> bool:
    return device.client == PS3_DEVICE_TYPE.client


def title_id_of(name: str) -> str | None:
    """The title id a save folder or game folder name starts with."""
    match = TITLE_ID_PATTERN.match(name)
    return match.group(0) if match else None


def normalize_title_id(value: str) -> str:
    """A title id without the dash some sources write (``BLES-01138``)."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _bracketed_title_id(name: str) -> str | None:
    match = _BRACKETED_TITLE_ID.search(name)
    return f"{match.group(1)}{match.group(2)}".upper() if match else None


def _sfo_title_id(data: bytes) -> str | None:
    try:
        title_id = parse_sfo(data).get("TITLE_ID")
    except ValueError:
        return None
    if not isinstance(title_id, str):
        return None
    return title_id_of(normalize_title_id(title_id))


class _TitleReader:
    def __init__(self, ftp: AsyncPS3Ftp, device_id: str) -> None:
        self.ftp = ftp
        self.device_id = device_id

    async def _cached(
        self,
        path: str,
        entry: FtpEntry,
        read: Callable[[], Awaitable[str | None]],
    ) -> str | None:
        stamp = entry.modified.isoformat() if entry.modified else ""
        key = f"romm:ps3_sync:{self.device_id}:title:{path}:{entry.size}:{stamp}"
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

        def read_sfo(ftp: PS3Ftp) -> bytes | None:
            return Iso9660(FtpFileReader(ftp, path)).read_file(
                "PS3_GAME/PARAM.SFO", _PARAM_SFO_MAX_BYTES
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
                    f"{path}/PS3_GAME/PARAM.SFO", _PARAM_SFO_MAX_BYTES
                )
            except _TITLE_READ_ERRORS as exc:
                log.debug(f"No PS3 title id in {hl(entry.display_name)}: {exc}")
                return None
            return _sfo_title_id(data)

        return await self._cached(path, entry, read)


_USER_FOLDER = re.compile(r"^\d{8}$")


# The name the console shows for a profile, a few bytes of UTF-8.
_USER_NAME_MAX_BYTES = 256


@dataclass(frozen=True)
class PS3UserProfile:
    id: str
    name: str | None


@dataclass(frozen=True)
class PS3ProbeResult:
    reachable: bool
    is_ftp: bool
    users: list[PS3UserProfile]


async def _user_name(ftp: AsyncPS3Ftp, user_id: str) -> str | None:
    try:
        raw = await ftp.read(
            f"/dev_hdd0/home/{user_id}/localusername", _USER_NAME_MAX_BYTES
        )
    except _READ_ERRORS:
        return None
    return raw.decode("utf-8", errors="replace").strip("\x00 \r\n") or None


async def probe_ps3(host: str, port: int) -> PS3ProbeResult:
    """Whether a PS3's FTP server answers at the address, and its user profiles."""
    greeting = await probe(host, port)
    if greeting is None:
        return PS3ProbeResult(reachable=False, is_ftp=False, users=[])
    try:
        ftp = await AsyncPS3Ftp.connect(host, port)
    except FTP_ERRORS:
        return PS3ProbeResult(reachable=True, is_ftp=False, users=[])
    try:
        homes = await _list_or_empty(ftp, "/dev_hdd0/home")
        ids = sorted(e.name for e in homes if e.is_dir and _USER_FOLDER.match(e.name))
        users = [PS3UserProfile(id=i, name=await _user_name(ftp, i)) for i in ids]
    except FTP_ERRORS:
        users = []
    finally:
        await ftp.close()
    return PS3ProbeResult(reachable=True, is_ftp=True, users=users)


async def _list_or_empty(ftp: AsyncPS3Ftp, path: str) -> list[FtpEntry]:
    try:
        return await ftp.list(path)
    except ftplib.error_perm:
        return []


async def discover_title_ids(ftp: AsyncPS3Ftp, device_id: str) -> set[str]:
    """Title ids of the games on the console: ISOs, game folders and installs."""
    reader = _TitleReader(ftp, device_id)
    title_ids: set[str] = set()

    for root in _GAME_ROOTS:
        folders = {
            entry.name.upper(): entry.name
            for entry in await _list_or_empty(ftp, root)
            if entry.is_dir
        }

        # Installed games, game data and updates, each in a folder named by id.
        if "GAME" in folders:
            for entry in await _list_or_empty(ftp, f"{root}/{folders['GAME']}"):
                if entry.is_dir and (title_id := title_id_of(entry.name)):
                    title_ids.add(title_id)

        if "PS3ISO" in folders:
            iso_dir = f"{root}/{folders['PS3ISO']}"
            for entry in await _list_or_empty(ftp, iso_dir):
                if not entry.is_dir and _ISO_NAME.search(entry.name):
                    path = f"{iso_dir}/{entry.name}"
                    if title_id := await reader.from_iso(path, entry):
                        title_ids.add(title_id)

        if "GAMES" in folders:
            games_dir = f"{root}/{folders['GAMES']}"
            for entry in await _list_or_empty(ftp, games_dir):
                if entry.is_dir:
                    path = f"{games_dir}/{entry.name}"
                    if title_id := await reader.from_folder(path, entry):
                        title_ids.add(title_id)

    return title_ids
