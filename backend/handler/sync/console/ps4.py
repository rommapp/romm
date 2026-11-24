"""Where a PS4 running GoldHEN's FTP server keeps its games and saves."""

from __future__ import annotations

import re

from handler.sync.console.common import (
    ConsoleProfile,
    read_sfo_field,
    title_id_of,
    title_ids_in,
)
from handler.sync.console.ftp import AsyncConsoleFtp, FtpEntry
from models.device import KNOWN_DEVICES
from utils.platform_slugs import UniversalPlatformSlug as UPS

# A title's saves share one folder, so the folder is the title id alone.
SAVE_FOLDER_PATTERN = re.compile(r"^[A-Z]{4}\d{5}$")
_IMAGE_PREFIX = "sdimg_"
_KEY_SUFFIX = ".bin"

# Installed games on the internal drive and on extended storage.
_APP_ROOTS = ("/user/app", "/mnt/ext0/user/app", "/mnt/ext1/user/app")


def is_save(names: set[str]) -> bool:
    """Whether the files are encrypted save images, each with its sealed key."""
    images = {
        n.removeprefix(_IMAGE_PREFIX) for n in names if n.startswith(_IMAGE_PREFIX)
    }
    keys = {n.removesuffix(_KEY_SUFFIX) for n in names if n.endswith(_KEY_SUFFIX)}
    return bool(images) and images == keys and len(names) == 2 * len(images)


async def discover_title_ids(ftp: AsyncConsoleFtp, device_id: str) -> set[str]:
    """Title ids of the games installed on the console."""
    title_ids: set[str] = set()
    for root in _APP_ROOTS:
        title_ids |= await title_ids_in(ftp, root)
    return title_ids


async def _save_title(
    ftp: AsyncConsoleFtp, folder_path: str, files: list[FtpEntry]
) -> str | None:
    # Saves are encrypted, so the title comes from the installed game's metadata.
    title_id = title_id_of(folder_path.rsplit("/", 1)[-1])
    if not title_id:
        return None
    return await read_sfo_field(
        ftp, f"/system_data/priv/appmeta/{title_id}/param.sfo", "TITLE"
    )


PS4 = ConsoleProfile(
    device_type=KNOWN_DEVICES["ps4"],
    platform_slug=UPS.PS4,
    title="PlayStation 4",
    default_ftp_port=2121,
    home_root="/user/home",
    user_pattern=re.compile(r"^[0-9a-f]{8}$"),
    user_name_file="username.dat",
    save_folder_pattern=SAVE_FOLDER_PATTERN,
    folder_max_bytes=2 * 1024 * 1024 * 1024,
    is_save=is_save,
    discover_title_ids=discover_title_ids,
    save_title=_save_title,
)
