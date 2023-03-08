import os
import shutil
from pathlib import Path

import requests
from fastapi import HTTPException

from config.config import EMULATION_BASE_PATH
from logger.logger import log


def get_platforms() -> list:
    """Gets all filesystem platforms
    
    Returns list with all the filesystem platforms found in the PLATFORMS_BASE_PATH.
    Automatically discards the default directory.
    """
    try:
        log.debug(EMULATION_BASE_PATH)
        platforms: list = list(os.walk(EMULATION_BASE_PATH))[0][1]
        log.debug(platforms)
        if 'defaults' in platforms: platforms.remove('defaults')
        log.info(f"filesystem platforms found: {platforms}")
        return platforms
    except IndexError:
        raise HTTPException(status_code=404, detail="Platforms not found.")
    

def platform_exists(slug: str) -> bool:
    """Check if platforms exists in the system
    
    Args:
        slug: shor name of the platform

    Returns True if platform exists in the filesystem, else False
    """
    try:
        platforms: list = get_platforms()
        exists: bool = True if slug in platforms else False
    except IndexError:
        exists: bool = False
    return exists


def platform_logo_exists(slug: str) -> bool:
    """Check if platform logo exists in filesystem
    
    Args:
        slug: shor name of the platform
    Returns
        True if logo exists in filesystem else False
    """
    logo_path: str = f"{EMULATION_BASE_PATH}/{slug}/resources/logo.png"
    return True if os.path.exists(logo_path) else False


def get_platform_logo_path(slug: str) -> str:
    return f"{EMULATION_BASE_PATH}/{slug}/resources/logo.png"


def store_platform_logo(slug: str, url_logo: str) -> None:
    """Store platform resources in filesystem
    
    Args:
        slug: shor name of the platform
        url_logo: url to get logo
    """
    file_ext: str = url_logo.split('.')[-1]
    logo_file: str = f"logo.{file_ext}"
    logo_path: str = f"{EMULATION_BASE_PATH}/{slug}/resources"
    res = requests.get(url_logo, stream=True)
    if res.status_code == 200:
        Path(logo_path).mkdir(parents=True, exist_ok=True)
        with open(f"{logo_path}/{logo_file}", 'wb') as f:
            shutil.copyfileobj(res.raw, f)
        log.info(f"{slug} logo downloaded successfully!")
    else:
        log.warning(f"{slug} logo couldn't be downloaded")


def platform_have_roms(slug: str) -> bool:
    """Check if the platform have the roms folder
    
    Args:
        slug: shor name of the platform

    Returns True if roms folder have roms, else False
    """
    return True if list(os.walk(f"{EMULATION_BASE_PATH}/{slug}/roms")) else False
