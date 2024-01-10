import datetime
import fnmatch
import os
import shutil
from enum import Enum
from pathlib import Path
from urllib.parse import quote
from PIL import Image
from typing import Final

import requests
from config import (
    LIBRARY_BASE_PATH,
    ROMM_BASE_PATH,
    DEFAULT_URL_COVER_L,
    DEFAULT_PATH_COVER_L,
    DEFAULT_URL_COVER_S,
    DEFAULT_PATH_COVER_S,
)
from config.config_manager import config
from exceptions.fs_exceptions import (
    PlatformsNotFoundException,
    RomAlreadyExistsException,
    RomsNotFoundException,
)

from . import get_file_extension

RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
DEFAULT_WIDTH_COVER_L: Final = 264  # Width of big cover of IGDB
DEFAULT_HEIGHT_COVER_L: Final = 352  # Height of big cover of IGDB
DEFAULT_WIDTH_COVER_S: Final = 90  # Width of small cover of IGDB
DEFAULT_HEIGHT_COVER_S: Final = 120  # Height of small cover of IGDB


# ========= Resources utils =========
class CoverSize(Enum):
    SMALL = "small"
    BIG = "big"


def _cover_exists(fs_slug: str, rom_name: str, size: CoverSize):
    """Check if rom cover exists in filesystem

    Args:
        fs_slug: short name of the platform
        rom_name: name of rom file
        size: size of the cover
    Returns
        True if cover exists in filesystem else False
    """
    return bool(
        os.path.exists(
            f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover/{size.value}.png"
        )
    )


def _resize_cover(cover_path: str, size: CoverSize) -> None:
    """Resizes the cover image to the standard size

    Args:
        cover_path: path where the original cover were stored
        size: size of the cover
    """
    cover = Image.open(cover_path)
    if cover.size[1] > DEFAULT_HEIGHT_COVER_L:
        if size == CoverSize.BIG:
            big_dimensions = (DEFAULT_WIDTH_COVER_L, DEFAULT_HEIGHT_COVER_L)
            background = Image.new("RGBA", big_dimensions, (0, 0, 0, 0))
            cover.thumbnail(big_dimensions)
            offset = (int(round(((DEFAULT_WIDTH_COVER_L - cover.size[0]) / 2), 0)), 0)
        elif size == CoverSize.SMALL:
            small_dimensions = (DEFAULT_WIDTH_COVER_S, DEFAULT_HEIGHT_COVER_S)
            background = Image.new("RGBA", small_dimensions, (0, 0, 0, 0))
            cover.thumbnail(small_dimensions)
            offset = (int(round(((DEFAULT_WIDTH_COVER_S - cover.size[0]) / 2), 0)), 0)
        else:
            return
        background.paste(cover, offset)
        background.save(cover_path)


def _store_cover(fs_slug: str, rom_name: str, url_cover: str, size: CoverSize):
    """Store roms resources in filesystem

    Args:
        fs_slug: short name of the platform
        rom_name: name of rom file
        url_cover: url to get the cover
        size: size of the cover
    """
    cover_file = f"{size.value}.png"
    cover_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover"
    res = requests.get(
        url_cover.replace("t_thumb", f"t_cover_{size.value}"), stream=True, timeout=120
    )
    if res.status_code == 200:
        Path(cover_path).mkdir(parents=True, exist_ok=True)
        with open(f"{cover_path}/{cover_file}", "wb") as f:
            shutil.copyfileobj(res.raw, f)
        _resize_cover(f"{cover_path}/{cover_file}", size)


def _get_cover_path(fs_slug: str, rom_name: str, size: CoverSize):
    """Returns rom cover filesystem path adapted to frontend folder structure

    Args:
        fs_slug: short name of the platform
        file_name: name of rom file
        size: size of the cover
    """
    strtime = str(datetime.datetime.now().timestamp())
    return f"{fs_slug}/{rom_name}/cover/{size.value}.png?timestamp={strtime}"


def get_rom_cover(
    overwrite: bool, fs_slug: str, rom_name: str, url_cover: str = ""
) -> dict:
    q_rom_name = quote(rom_name)
    # Cover small
    if (
        overwrite or not _cover_exists(fs_slug, rom_name, CoverSize.SMALL)
    ) and url_cover:
        _store_cover(fs_slug, rom_name, url_cover, CoverSize.SMALL)
    path_cover_s = (
        _get_cover_path(fs_slug, q_rom_name, CoverSize.SMALL)
        if _cover_exists(fs_slug, rom_name, CoverSize.SMALL)
        else DEFAULT_PATH_COVER_S
    )

    # Cover big
    if (overwrite or not _cover_exists(fs_slug, rom_name, CoverSize.BIG)) and url_cover:
        _store_cover(fs_slug, rom_name, url_cover, CoverSize.BIG)
    path_cover_l = (
        _get_cover_path(fs_slug, q_rom_name, CoverSize.BIG)
        if _cover_exists(fs_slug, rom_name, CoverSize.BIG)
        else DEFAULT_PATH_COVER_L
    )

    return {
        "path_cover_s": path_cover_s,
        "path_cover_l": path_cover_l,
    }


def _store_screenshot(fs_slug: str, rom_name: str, url: str, idx: int):
    """Store roms resources in filesystem

    Args:
        fs_slug: short name of the platform
        file_name: name of rom
        url: url to get the screenshot
    """
    screenshot_file: str = f"{idx}.jpg"
    screenshot_path: str = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/screenshots"
    res = requests.get(url, stream=True, timeout=120)
    if res.status_code == 200:
        Path(screenshot_path).mkdir(parents=True, exist_ok=True)
        with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
            shutil.copyfileobj(res.raw, f)


def _get_screenshot_path(fs_slug: str, rom_name: str, idx: str):
    """Returns rom cover filesystem path adapted to frontend folder structure

    Args:
        fs_slug: short name of the platform
        file_name: name of rom
        idx: index number of screenshot
    """
    return f"{fs_slug}/{rom_name}/screenshots/{idx}.jpg"


def get_rom_screenshots(fs_slug: str, rom_name: str, url_screenshots: list) -> dict:
    q_rom_name = quote(rom_name)

    path_screenshots: list[str] = []
    for idx, url in enumerate(url_screenshots):
        _store_screenshot(fs_slug, rom_name, url, idx)
        path_screenshots.append(_get_screenshot_path(fs_slug, q_rom_name, str(idx)))

    return {"path_screenshots": path_screenshots}


def store_default_resources():
    """Store default cover resources in the filesystem"""
    defaul_covers = [
        {"url": DEFAULT_URL_COVER_L, "size": CoverSize.BIG},
        {"url": DEFAULT_URL_COVER_S, "size": CoverSize.SMALL},
    ]
    for cover in defaul_covers:
        if not _cover_exists("default", "default", cover["size"]):
            _store_cover("default", "default", cover["url"], cover["size"])


# ========= Platforms utils =========
def _exclude_platforms(platforms: list):
    return [
        platform for platform in platforms if platform not in config.EXCLUDED_PLATFORMS
    ]


def get_platforms() -> list[str]:
    """Gets all filesystem platforms

    Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
    Automatically exclude folders defined in user config.
    """
    try:
        platforms: list[str] = (
            list(os.walk(config.HIGH_PRIO_STRUCTURE_PATH))[0][1]
            if os.path.exists(config.HIGH_PRIO_STRUCTURE_PATH)
            else list(os.walk(LIBRARY_BASE_PATH))[0][1]
        )
        return _exclude_platforms(platforms)
    except IndexError as exc:
        raise PlatformsNotFoundException from exc


# ========= Roms utils =========
def get_fs_structure(fs_slug: str, folder: str = config.ROMS_FOLDER_NAME):
    return (
        f"{folder}/{fs_slug}"
        if os.path.exists(config.HIGH_PRIO_STRUCTURE_PATH)
        else f"{fs_slug}/{folder}"
    )


def _exclude_files(files, filetype) -> list[str]:
    excluded_extensions = getattr(config, f"EXCLUDED_{filetype.upper()}_EXT")
    excluded_names = getattr(config, f"EXCLUDED_{filetype.upper()}_FILES")
    excluded_files: list = []

    for file_name in files:
        # Split the file name to get the extension.
        ext = get_file_extension(file_name)

        # Exclude the file if it has no extension or the extension is in the excluded list.
        if not ext or ext in excluded_extensions:
            excluded_files.append(file_name)

        # Additionally, check if the file name mathes a pattern in the excluded list.
        if len(excluded_names) > 0:
            [
                excluded_files.append(file_name)
                for name in excluded_names
                if file_name == name or fnmatch.fnmatch(file_name, name)
            ]

    # Return files that are not in the filtered list.
    return [f for f in files if f not in excluded_files]


def _exclude_multi_roms(roms) -> list[str]:
    excluded_names = config.EXCLUDED_MULTI_FILES
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


def get_roms(fs_slug: str):
    """Gets all filesystem roms for a platform

    Args:
        fs_slug: short name of the platform
    Returns:
        list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH
    """
    roms_path = get_fs_structure(fs_slug)
    roms_file_path = f"{LIBRARY_BASE_PATH}/{roms_path}"

    try:
        fs_single_roms: list[str] = list(os.walk(roms_file_path))[0][2]
    except IndexError as exc:
        raise RomsNotFoundException(fs_slug) from exc

    try:
        fs_multi_roms: list[str] = list(os.walk(roms_file_path))[0][1]
    except IndexError as exc:
        raise RomsNotFoundException(fs_slug) from exc

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


def get_assets(platform_slug: str):
    saves_path = get_fs_structure(platform_slug, folder=config.SAVES_FOLDER_NAME)
    saves_file_path = f"{LIBRARY_BASE_PATH}/{saves_path}"

    fs_saves: list[str] = []
    fs_states: list[str] = []
    fs_screenshots: list[str] = []

    try:
        emulators = list(os.walk(saves_file_path))[0][1]
        for emulator in emulators:
            fs_saves += [
                (emulator, file)
                for file in list(os.walk(f"{saves_file_path}/{emulator}"))[0][2]
            ]

        fs_saves += [(None, file) for file in list(os.walk(saves_file_path))[0][2]]
    except IndexError:
        pass

    states_path = get_fs_structure(platform_slug, folder=config.STATES_FOLDER_NAME)
    states_file_path = f"{LIBRARY_BASE_PATH}/{states_path}"

    try:
        emulators = list(os.walk(states_file_path))[0][1]
        for emulator in emulators:
            fs_states += [
                (emulator, file)
                for file in list(os.walk(f"{states_file_path}/{emulator}"))[0][2]
            ]

        fs_states += [(None, file) for file in list(os.walk(states_file_path))[0][2]]
    except IndexError:
        pass

    screenshots_path = get_fs_structure(
        platform_slug, folder=config.SCREENSHOTS_FOLDER_NAME
    )
    screenshots_file_path = f"{LIBRARY_BASE_PATH}/{screenshots_path}"

    try:
        fs_screenshots += [file for file in list(os.walk(screenshots_file_path))[0][2]]
    except IndexError:
        pass

    return {
        "saves": fs_saves,
        "states": fs_states,
        "screenshots": fs_screenshots,
    }


def get_screenshots():
    screenshots_path = f"{LIBRARY_BASE_PATH}/{config.SCREENSHOTS_FOLDER_NAME}"

    fs_screenshots = []

    try:
        platforms = list(os.walk(screenshots_path))[0][1]
        for platform in platforms:
            fs_screenshots += [
                (platform, file)
                for file in list(os.walk(f"{screenshots_path}/{platform}"))[0][2]
            ]

        fs_screenshots += [
            (None, file) for file in list(os.walk(screenshots_path))[0][2]
        ]
    except IndexError:
        pass

    return fs_screenshots


def get_rom_file_size(
    roms_path: str, file_name: str, multi: bool, multi_files: list = []
):
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


def get_fs_file_size(asset_path: str, file_name: str):
    return os.stat(f"{LIBRARY_BASE_PATH}/{asset_path}/{file_name}").st_size


def _file_exists(path: str, file_name: str):
    """Check if file exists in filesystem

    Args:
        path: path to file
        file_name: name of file
    Returns
        True if file exists in filesystem else False
    """
    return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{path}/{file_name}"))


def rename_file(old_name: str, new_name: str, file_path: str):
    if new_name != old_name:
        if _file_exists(path=file_path, file_name=new_name):
            raise RomAlreadyExistsException(new_name)

        os.rename(
            f"{LIBRARY_BASE_PATH}/{file_path}/{old_name}",
            f"{LIBRARY_BASE_PATH}/{file_path}/{new_name}",
        )


def remove_file(file_name: str, file_path: str):
    try:
        os.remove(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")
    except IsADirectoryError:
        shutil.rmtree(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")


def build_upload_file_path(fs_slug: str, folder: str = config.ROMS_FOLDER_NAME):
    rom_path = get_fs_structure(fs_slug, folder=folder)
    return f"{LIBRARY_BASE_PATH}/{rom_path}"


def build_artwork_path(rom_name: str, fs_slug: str, file_ext: str):
    q_rom_name = quote(rom_name)
    strtime = str(datetime.datetime.now().timestamp())

    path_cover_l = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.BIG.value}.{file_ext}?timestamp={strtime}"
    path_cover_s = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.SMALL.value}.{file_ext}?timestamp={strtime}"
    artwork_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover"
    Path(artwork_path).mkdir(parents=True, exist_ok=True)
    return path_cover_l, path_cover_s, artwork_path


# ========= Users utils =========
def build_avatar_path(avatar_path: str, username: str):
    avatar_user_path = f"{RESOURCES_BASE_PATH}/users/{username}"
    Path(avatar_user_path).mkdir(parents=True, exist_ok=True)
    return f"users/{username}/{avatar_path}", avatar_user_path
