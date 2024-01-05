import os
from enum import Enum
import shutil
from pathlib import Path
import datetime
import requests
from urllib.parse import quote
from PIL import Image

from config import (
    LIBRARY_BASE_PATH,
    HIGH_PRIO_STRUCTURE_PATH,
    ROMS_FOLDER_NAME,
    RESOURCES_BASE_PATH,
    DEFAULT_URL_COVER_L,
    DEFAULT_PATH_COVER_L,
    DEFAULT_WIDTH_COVER_L,
    DEFAULT_HEIGHT_COVER_L,
    DEFAULT_URL_COVER_S,
    DEFAULT_PATH_COVER_S,
    DEFAULT_WIDTH_COVER_S,
    DEFAULT_HEIGHT_COVER_S,
)
from config.config_loader import config
from exceptions.fs_exceptions import (
    PlatformsNotFoundException,
    PlatformNotFoundException,
    RomsNotFoundException,
    RomNotFoundError,
    RomAlreadyExistsException,
)


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


def get_cover(
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


def get_screenshots(fs_slug: str, rom_name: str, url_screenshots: list) -> dict:
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


def remove_platform(fs_slug: str):
    platform_path = get_roms_structure(fs_slug)
    try:
        shutil.rmtree(f"{LIBRARY_BASE_PATH}/{platform_path}")
    except FileNotFoundError as exc:
        raise PlatformNotFoundException(fs_slug) from exc    


# ========= Roms utils =========
def get_roms_structure(fs_slug: str):
    return (
        f"{ROMS_FOLDER_NAME}/{fs_slug}"
        if os.path.exists(HIGH_PRIO_STRUCTURE_PATH)
        else f"{fs_slug}/{ROMS_FOLDER_NAME}"
    )


def _exclude_files(files, filetype) -> list[str]:
    excluded_extensions = config[f"EXCLUDED_{filetype.upper()}_EXT"]
    excluded_names = config[f"EXCLUDED_{filetype.upper()}_FILES"]
    filtered_files: list = []

    for file in files:
        # Exclude files starting with a period.
        if file.startswith('.'):
            filtered_files.append(file)
        else:
            # Split the file name to get the extension.
            parts = file.split(".")
            # Exclude the file if it has no extension or the extension is in the excluded list.
            if len(parts) == 1 or parts[-1] in excluded_extensions:
                filtered_files.append(file)
            # Additionally, check if the entire file name is in the excluded names list.
            elif file in excluded_names:
                filtered_files.append(file)

    # Return files that are not in the filtered list.
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


def get_roms(fs_slug: str):
    """Gets all filesystem roms for a platform

    Args:
        fs_slug: short name of the platform
    Returns:
        list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH
    """
    roms_path = get_roms_structure(fs_slug)
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


def _rom_exists(fs_slug: str, file_name: str):
    """Check if rom exists in filesystem

    Args:
        fs_slug: short name of the platform
        file_name: rom file_name
    Returns
        True if rom exists in filesystem else False
    """
    rom_path = get_roms_structure(fs_slug)
    return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}"))


def rename_rom(fs_slug: str, old_name: str, new_name: str):
    if new_name != old_name:
        rom_path = get_roms_structure(fs_slug)
        if _rom_exists(fs_slug, new_name):
            raise RomAlreadyExistsException(new_name)
        os.rename(
            f"{LIBRARY_BASE_PATH}/{rom_path}/{old_name}",
            f"{LIBRARY_BASE_PATH}/{rom_path}/{new_name}",
        )


def remove_rom(fs_slug: str, file_name: str):
    rom_path = get_roms_structure(fs_slug)
    try:
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{rom_path}/{file_name}")
    except FileNotFoundError as exc:
        raise RomNotFoundError(file_name, fs_slug) from exc


def build_upload_roms_path(fs_slug: str):
    rom_path = get_roms_structure(fs_slug)
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
