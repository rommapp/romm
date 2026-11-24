"""What syncing any console over FTP shares, and the profile each kind fills in."""

from __future__ import annotations

# Consoles serve their files over plain FTP only, and only on the LAN.
import ftplib  # nosec B402
import ipaddress
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Final

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from config import MAX_AUTOCLEANUP_LIMIT
from handler.sync.console.ftp import (
    FTP_ERRORS,
    AsyncConsoleFtp,
    FtpEntry,
    FtpFileTooLarge,
    probe,
)
from handler.sync.retroarch.psp import parse_sfo
from models.device import DeviceType
from utils.platform_slugs import UniversalPlatformSlug as UPS
from utils.ssrf import is_lan_ip

CACHE_PREFIX = "romm:console_sync"

TITLE_ID_PATTERN = re.compile(r"^[A-Z]{4}\d{5}")
PARAM_SFO_MAX_BYTES = 64 * 1024
READ_ERRORS: Final[tuple[type[Exception], ...]] = (FtpFileTooLarge, *FTP_ERRORS)

# The name the console shows for a profile, a few bytes of UTF-8.
_USER_NAME_MAX_BYTES = 256


@dataclass(frozen=True)
class ConsoleProfile:
    """Where a kind of console keeps its user profiles, games and saves."""

    device_type: DeviceType
    platform_slug: UPS
    title: str
    default_ftp_port: int
    home_root: str
    user_pattern: re.Pattern[str]
    user_name_file: str
    save_folder_pattern: re.Pattern[str]
    folder_max_bytes: int
    # Whether the file names of a stored version make up one of its saves.
    is_save: Callable[[set[str]], bool]
    # Title ids of the games on the console, given the session and device id.
    discover_title_ids: Callable[[AsyncConsoleFtp, str], Awaitable[set[str]]]
    # The game title a save folder names, given its path and files.
    save_title: Callable[[AsyncConsoleFtp, str, list[FtpEntry]], Awaitable[str | None]]

    @property
    def kind(self) -> str:
        return self.device_type.client

    def savedata_path(self, user_id: str) -> str:
        return f"{self.home_root}/{user_id}/savedata"


FtpPort = Annotated[int, Field(ge=1, le=65535)]
ConsoleUserId = Annotated[
    str,
    Field(
        pattern=r"^[0-9A-Za-z]{1,16}$",
        description="The console user profile whose saves are synced.",
    ),
]
PollIntervalMinutes = Annotated[int, Field(ge=1, le=24 * 60)]
KeepVersions = Annotated[int, Field(ge=1, le=MAX_AUTOCLEANUP_LIMIT)]


class ConsoleSyncConfig(BaseModel):
    """What `Device.sync_config` holds for a console; its address is `Device.ip_address`."""

    ftp_port: FtpPort
    user_id: ConsoleUserId
    poll_interval_minutes: PollIntervalMinutes = 15
    keep_versions: KeepVersions = 10

    @classmethod
    def of(
        cls, profile: ConsoleProfile, sync_config: dict[str, Any] | None
    ) -> ConsoleSyncConfig:
        return cls.model_validate(
            {"ftp_port": profile.default_ftp_port, **(sync_config or {})},
            context={"profile": profile},
        )

    @model_validator(mode="after")
    def _user_of_the_console(self, info: ValidationInfo) -> ConsoleSyncConfig:
        profile = (info.context or {}).get("profile")
        if profile and not profile.user_pattern.fullmatch(self.user_id):
            raise ValueError(f"{self.user_id} is not a {profile.title} user profile")
        return self


def is_lan_address(address: str | None) -> bool:
    """Whether a stored console address is one the server may connect to."""
    try:
        return address is not None and is_lan_ip(ipaddress.ip_address(address))
    except ValueError:
        return False


def title_id_of(name: str) -> str | None:
    """The title id a save folder or game folder name starts with."""
    match = TITLE_ID_PATTERN.match(name)
    return match.group(0) if match else None


def normalize_title_id(value: str) -> str:
    """A title id without the dash some sources write (``BLES-01138``)."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def sfo_field(data: bytes, key: str) -> str | None:
    try:
        value = parse_sfo(data).get(key)
    except ValueError:
        return None
    return value if isinstance(value, str) else None


async def read_sfo_field(ftp: AsyncConsoleFtp, path: str, key: str) -> str | None:
    try:
        data = await ftp.read(path, PARAM_SFO_MAX_BYTES)
    except READ_ERRORS:
        return None
    return sfo_field(data, key)


async def list_or_empty(ftp: AsyncConsoleFtp, path: str) -> list[FtpEntry]:
    try:
        return await ftp.list(path)
    except ftplib.error_perm:
        return []


async def title_ids_in(ftp: AsyncConsoleFtp, path: str) -> set[str]:
    """Title ids of the folders in `path` named by one."""
    return {
        title_id
        for entry in await list_or_empty(ftp, path)
        if entry.is_dir and (title_id := title_id_of(entry.name))
    }


@dataclass(frozen=True)
class ConsoleUserProfile:
    id: str
    name: str | None


@dataclass(frozen=True)
class ConsoleProbeResult:
    reachable: bool
    is_ftp: bool
    users: list[ConsoleUserProfile]


async def _user_name(
    ftp: AsyncConsoleFtp, profile: ConsoleProfile, user_id: str
) -> str | None:
    try:
        raw = await ftp.read(
            f"{profile.home_root}/{user_id}/{profile.user_name_file}",
            _USER_NAME_MAX_BYTES,
        )
    except READ_ERRORS:
        return None
    return raw.decode("utf-8", errors="replace").strip("\x00 \r\n") or None


async def probe_console_ftp(
    profile: ConsoleProfile, host: str, port: int
) -> ConsoleProbeResult:
    """Whether a console's FTP server answers at the address, and its user profiles."""
    greeting = await probe(host, port)
    if greeting is None:
        return ConsoleProbeResult(reachable=False, is_ftp=False, users=[])
    try:
        ftp = await AsyncConsoleFtp.connect(host, port)
    except FTP_ERRORS:
        return ConsoleProbeResult(reachable=True, is_ftp=False, users=[])
    try:
        homes = await list_or_empty(ftp, profile.home_root)
        ids = sorted(
            e.name for e in homes if e.is_dir and profile.user_pattern.fullmatch(e.name)
        )
        users = [
            ConsoleUserProfile(id=i, name=await _user_name(ftp, profile, i))
            for i in ids
        ]
    except FTP_ERRORS:
        users = []
    finally:
        await ftp.close()
    return ConsoleProbeResult(reachable=True, is_ftp=True, users=users)
