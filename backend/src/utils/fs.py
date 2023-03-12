import os
import shutil
from pathlib import Path

import requests
from fastapi import HTTPException

from config.config import EMULATION_BASE_PATH
from logger.logger import log


def get_platforms() -> list:
    """Gets all filesystem platforms
    
    Returns list with all the filesystem platforms found in the EMULATION_BASE_PATH.
    Automatically discards the default directory.
    """
    try:
        platforms: list = list(os.walk(EMULATION_BASE_PATH))[0][1]
        if 'resources' in platforms: platforms.remove('resources')
        log.info(f"filesystem platforms found: {platforms}")
        return platforms
    except IndexError:
        raise HTTPException(status_code=404, detail="Platforms not found.")


def platform_logo_exists(slug: str) -> bool:
    """Check if platform logo exists in filesystem
    
    Args:
        slug: shor name of the platform
    Returns
        True if logo exists in filesystem else False
    """
    logo_path: str = f"{EMULATION_BASE_PATH}/resources/{slug}/logo.png"
    return True if os.path.exists(logo_path) else False


def get_platform_logo_path(slug: str) -> str:
    return f"/assets/emulation/resources/{slug}/logo.png"


def store_platform_logo(platform_slug: str, url_logo: str) -> None:
    """Store platform resources in filesystem
    
    Args:
        slug: shor name of the platform
        url_logo: url to get logo
    """
    logo_file: str = f"logo.png"
    logo_path: str = f"{EMULATION_BASE_PATH}/resources/{platform_slug}"
    res = requests.get(url_logo, stream=True)
    if res.status_code == 200:
        Path(logo_path).mkdir(parents=True, exist_ok=True)
        with open(f"{logo_path}/{logo_file}", 'wb') as f:
            shutil.copyfileobj(res.raw, f)
        log.info(f"{platform_slug} logo downloaded successfully!")
    else:
        log.warning(f"{platform_slug} logo couldn't be downloaded")


def get_roms(platform_slug) -> list:
    """Gets all filesystem roms for a platform
    
    Returns list with all the filesystem roms for a platform found in the EMULATION_BASE_PATH.
    Automatically discards the default directory.
    """
    try:
        roms: list = []
        roms = list(os.walk(f"{EMULATION_BASE_PATH}/{platform_slug}/roms/"))[0][2]
        log.info(f"filesystem roms found for {platform_slug}: {roms}")
    except IndexError:
        log.warning(f"roms not found for {platform_slug}")
        pass
    return roms


def rom_cover_exists(platform_slug: str, rom_filename: str, size: str) -> bool:
    """Check if rom cover exists in filesystem
    
    Args:
        slug: short name of the platform
        rom_filename: name of rom file
    Returns
        True if cover exists in filesystem else False
    """
    logo_path: str = f"{EMULATION_BASE_PATH}/resources/{platform_slug}/{rom_filename.split('.')[0]}_{size}.png"
    return True if os.path.exists(logo_path) else False


def get_rom_cover_path(platform_slug: str, rom_filename: str, size: str) -> str:
    return f"/assets/emulation/resources/{platform_slug}/{rom_filename.split('.')[0]}_{size}.png"


def store_rom_cover(platfom_slug: str, rom_filename: str, url_cover: str, size: str) -> None:
    """Store roms resources in filesystem
    
    Args:
        platform_slug: short name of the platform
        rom_filename: name of rom file
        url_cover: url to get cover
    """
    cover_file: str = f"{rom_filename.split('.')[0]}_{size}.png"
    cover_path: str = f"{EMULATION_BASE_PATH}/resources/{platfom_slug}/"
    res = requests.get(url_cover.replace('t_thumb', f't_cover_{size}'), stream=True)
    if res.status_code == 200:
        Path(cover_path).mkdir(parents=True, exist_ok=True)
        with open(f"{cover_path}/{cover_file}", 'wb') as f:
            shutil.copyfileobj(res.raw, f)
        log.info(f"{rom_filename} {size} cover downloaded successfully!")
    else:
        log.warning(f"{rom_filename} {size} cover couldn't be downloaded")