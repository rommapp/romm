import os
import shutil
from pathlib import Path
import datetime
import requests

from config import (
    LIBRARY_BASE_PATH,
    HIGH_PRIO_STRUCTURE_PATH,
    RESOURCES_BASE_PATH,
    DEFAULT_URL_COVER_L,
    DEFAULT_PATH_COVER_L,
    DEFAULT_URL_COVER_S,
    DEFAULT_PATH_COVER_S,
)
from config.config_loader import config
from exceptions.fs_exceptions import (
    PlatformsNotFoundException,
    RomsNotFoundException,
    RomNotFoundError,
    RomAlreadyExistsException,
)


# ========= Resources utils =========
def _cover_exists(p_slug: str, r_name: str, size: str):
    """Check if rom cover exists in filesystem

    Args:
        p_slug: short name of the platform
        r_name: name of rom file
        size: size of the cover -> big as 'l' | small as 's'
    Returns
        True if cover exists in filesystem else False
    """
    return bool(
        os.path.exists(f"{RESOURCES_BASE_PATH}/{p_slug}/{r_name}/cover/{size}.png")
    )


def _store_cover(p_slug: str, r_name: str, url_cover: str, size: str):
    """Store roms resources in filesystem

    Args:
        p_slug: short name of the platform
        r_name: name of rom file
        url_cover: url to get the cover
        size: size of the cover -> big | small
    """
    cover_file = f"{size}.png"
    cover_path = f"{RESOURCES_BASE_PATH}/{p_slug}/{r_name}/cover"
    res = requests.get(
        url_cover.replace("t_thumb", f"t_cover_{size}"), stream=True, timeout=120
    )
    if res.status_code == 200:
        Path(cover_path).mkdir(parents=True, exist_ok=True)
        with open(f"{cover_path}/{cover_file}", "wb") as f:
            shutil.copyfileobj(res.raw, f)


def _get_cover_path(p_slug: str, r_name: str, size: str):
    """Returns rom cover filesystem path adapted to frontend folder structure

    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        size: size of the cover -> big | small
    """
    strtime = str(datetime.datetime.now().timestamp())
    return f"{p_slug}/{r_name}/cover/{size}.png?timestamp={strtime}"


def get_cover(overwrite: bool, p_slug: str, r_name: str, url_cover: str = "") -> dict:
    # Cover small
    if (overwrite or not _cover_exists(p_slug, r_name, "small")) and url_cover:
        _store_cover(p_slug, r_name, url_cover, "small")
    path_cover_s = (
        _get_cover_path(p_slug, r_name, "small")
        if _cover_exists(p_slug, r_name, "small")
        else DEFAULT_PATH_COVER_S
    )

    # Cover big
    if (overwrite or not _cover_exists(p_slug, r_name, "big")) and url_cover:
        _store_cover(p_slug, r_name, url_cover, "big")
    (path_cover_l, has_cover) = (
        (_get_cover_path(p_slug, r_name, "big"), 1)
        if _cover_exists(p_slug, r_name, "big")
        else (DEFAULT_PATH_COVER_L, 0)
    )

    return {
        "path_cover_s": path_cover_s,
        "path_cover_l": path_cover_l,
        "has_cover": has_cover,
    }


def _store_screenshot(p_slug: str, r_name: str, url: str, idx: int):
    """Store roms resources in filesystem

    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        url: url to get the screenshot
    """
    screenshot_file: str = f"{idx}.jpg"
    screenshot_path: str = f"{RESOURCES_BASE_PATH}/{p_slug}/{r_name}/screenshots"
    res = requests.get(url, stream=True, timeout=120)
    if res.status_code == 200:
        Path(screenshot_path).mkdir(parents=True, exist_ok=True)
        with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
            shutil.copyfileobj(res.raw, f)


def _get_screenshot_path(p_slug: str, r_name: str, idx: str):
    """Returns rom cover filesystem path adapted to frontend folder structure

    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        idx: index number of screenshot
    """
    return f"{p_slug}/{r_name}/screenshots/{idx}.jpg"


def get_screenshots(p_slug: str, r_name: str, url_screenshots: list) -> dict:
    path_screenshots: list[str] = []
    for idx, url in enumerate(url_screenshots):
        _store_screenshot(p_slug, r_name, url, idx)
        path_screenshots.append(_get_screenshot_path(p_slug, r_name, str(idx)))
    return {"path_screenshots": path_screenshots}


def store_default_resources():
    """Store default cover resources in the filesystem"""
    defaul_covers = [
        {"url": DEFAULT_URL_COVER_L, "size": "big"},
        {"url": DEFAULT_URL_COVER_S, "size": "small"},
    ]
    for cover in defaul_covers:
        if not _cover_exists("default", "default", cover["size"]):
            _store_cover("default", "default", cover["url"], cover["size"])


# ========= Platforms utils =========
def _exclude_platforms(platforms: list):
    return [
        platform
        for platform in platforms
        if platform not in config["EXCLUDED_PLATFORMS"]
    ]


def get_platforms() -> list[str]:
    """Gets all filesystem platforms

    Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
    Automatically exclude folders defined in user config.
    """
    try:
        platforms: list[str] = (
            list(os.walk(HIGH_PRIO_STRUCTURE_PATH))[0][1]
            if os.path.exists(HIGH_PRIO_STRUCTURE_PATH)
            else list(os.walk(LIBRARY_BASE_PATH))[0][1]
        )
        return _exclude_platforms(platforms)
    except IndexError as exc:
        raise PlatformsNotFoundException from exc


# ========= Roms utils =========
def get_roms_structure(p_slug: str):
    return (
        f"roms/{p_slug}"
        if os.path.exists(HIGH_PRIO_STRUCTURE_PATH)
        else f"{p_slug}/roms"
    )


def _exclude_files(files, filetype) -> list[str]:
    excluded_extensions = config[f"EXCLUDED_{filetype.upper()}_EXT"]
    excluded_names = config[f"EXCLUDED_{filetype.upper()}_FILES"]
    filtered_files: list = []

    for file in files:
        if file.split(".")[-1] in excluded_extensions or file in excluded_names:
            filtered_files.append(file)

    return [f for f in files if f not in filtered_files]


def _exclude_multi_roms(roms) -> list[str]:
    excluded_names = config["EXCLUDED_MULTI_FILES"]
    filtered_files: list = []

    for rom in roms:
        if rom in excluded_names:
            filtered_files.append(rom)

    return [f for f in roms if f not in filtered_files]


def get_rom_files(rom: str, roms_path: str) -> list[str]:
    rom_files: list = []

    for path, _, files in os.walk(f"{roms_path}/{rom}"):
        for f in _exclude_files(files, "multi_parts"):
            rom_files.append(f"{Path(path, f)}".replace(f"{roms_path}/{rom}/", ""))

    return rom_files


def get_roms(p_slug: str):
    """Gets all filesystem roms for a platform

    Args:
        p_slug: short name of the platform
    Returns:
        list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH
    """
    roms_path = get_roms_structure(p_slug)
    roms_file_path = f"{LIBRARY_BASE_PATH}/{roms_path}"

    try:
        fs_single_roms: list[str] = list(os.walk(roms_file_path))[0][2]
    except IndexError as exc:
        raise RomsNotFoundException(p_slug) from exc

    try:
        fs_multi_roms: list[str] = list(os.walk(roms_file_path))[0][1]
    except IndexError as exc:
        raise RomsNotFoundException(p_slug) from exc

    fs_roms: list[dict] = [
        {"multi": False, "file_name": rom}
        for rom in _exclude_files(fs_single_roms, "single")
    ] + [
        {"multi": True, "file_name": rom} for rom in _exclude_multi_roms(fs_multi_roms)
    ]

    return [
        dict(
            rom,
            files=get_rom_files(rom["file_name"], roms_file_path),
        )
        for rom in fs_roms
    ]


def get_rom_size(roms_path: str, file_name: str, multi: bool, multi_files: list = []):
    files = (
        [f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}"]
        if not multi
        else [
            f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}/{file}"
            for file in multi_files
        ]
    )
    total_size: float = 0.0
    for file in files:
        total_size += os.stat(file).st_size
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if total_size < 1024.0 or unit == "PB":
            break
        total_size /= 1024.0
    return round(total_size, 2), unit


def _rom_exists(p_slug: str, file_name: str):
    """Check if rom exists in filesystem

    Args:
        p_slug: short name of the platform
        file_name: rom file_name
    Returns
        True if rom exists in filesystem else False
    """
    rom_path = get_roms_structure(p_slug)
    return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}"))


def rename_rom(p_slug: str, old_name: str, new_name: str):
    if new_name != old_name:
        rom_path = get_roms_structure(p_slug)
        if _rom_exists(p_slug, new_name):
            raise RomAlreadyExistsException(new_name)
        os.rename(
            f"{LIBRARY_BASE_PATH}/{rom_path}/{old_name}",
            f"{LIBRARY_BASE_PATH}/{rom_path}/{new_name}",
        )


def remove_rom(p_slug: str, file_name: str):
    rom_path = get_roms_structure(p_slug)
    try:
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}")
    except FileNotFoundError as exc:
        raise RomNotFoundError(file_name, p_slug) from exc


# ========= Users utils =========
def build_avatar_path(avatar_path, username):
    avatar_user_path = f"{RESOURCES_BASE_PATH}/users/{username}"
    Path(avatar_user_path).mkdir(parents=True, exist_ok=True)
    return f"users/{username}/{avatar_path}", avatar_user_path
