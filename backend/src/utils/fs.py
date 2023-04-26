import os
import shutil
from pathlib import Path

import requests

from config import user_config, LIBRARY_BASE_PATH, HIGH_PRIO_STRUCTURE_PATH, RESOURCES_BASE_PATH, DEFAULT_URL_COVER_L, DEFAULT_PATH_COVER_L, DEFAULT_URL_COVER_S, DEFAULT_PATH_COVER_S
from logger.logger import log
from utils.exceptions import PlatformsNotFoundException, RomsNotFoundException, RomNotFoundError, RomAlreadyExistsException


# ========= Resources utils =========
def _cover_exists(p_slug: str, file_name: str, size: str) -> bool:
    """Check if rom cover exists in filesystem
    
    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        size: size of the cover -> big as 'l' | small as 's'
    Returns
        True if cover exists in filesystem else False
    """
    logo_path: str = f"{RESOURCES_BASE_PATH}/{p_slug}/{file_name}_{size}.png"
    return True if os.path.exists(logo_path) else False


def _store_cover(p_slug: str, file_name: str, url_cover: str, size: str) -> None:
    """Store roms resources in filesystem
    
    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        url_cover: url to get the cover
        size: size of the cover -> big as 'l' | small as 's'
    """
    cover_file: str = f"{file_name}_{size}.png"
    cover_path: str = f"{RESOURCES_BASE_PATH}/{p_slug}/"
    sizes: dict = {'l': 'big', 's': 'small'}
    res = requests.get(url_cover.replace('t_thumb', f't_cover_{sizes[size]}'), stream=True)
    if res.status_code == 200:
        Path(cover_path).mkdir(parents=True, exist_ok=True)
        with open(f"{cover_path}/{cover_file}", 'wb') as f:
            shutil.copyfileobj(res.raw, f)
        log.info(f"{file_name} {sizes[size]} cover downloaded successfully!")
    else:
        log.error(f"{file_name} {sizes[size]} cover couldn't be downloaded")


def _get_cover_path(p_slug: str, file_name: str, size: str) -> str:
    """Returns rom cover filesystem path adapted to frontend folder structure
    
    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        size: size of the cover -> big as 'l' | small as 's'
    """
    return f"{RESOURCES_BASE_PATH}/{p_slug}/{file_name}_{size}.png"


def get_cover(overwrite: bool, p_slug: str, file_name: str, url_cover: str) -> tuple:
    path_cover_s: str = DEFAULT_PATH_COVER_S
    path_cover_l: str = DEFAULT_PATH_COVER_L
    has_cover: int = 0
    if (overwrite or not _cover_exists(p_slug, file_name, 's')) and url_cover:
        _store_cover(p_slug, file_name, url_cover, 's')
    if _cover_exists(p_slug, file_name, 's'):
        path_cover_s = _get_cover_path(p_slug, file_name, 's')
    
    if (overwrite or not _cover_exists(p_slug, file_name, 'l')) and url_cover:
        _store_cover(p_slug, file_name, url_cover, 'l')
    if _cover_exists(p_slug, file_name, 'l'):
        path_cover_l = _get_cover_path(p_slug, file_name, 'l')
        has_cover = 1
    return {'path_cover_s': path_cover_s, 'path_cover_l': path_cover_l, 'has_cover': has_cover}


def store_default_resources() -> None:
    """Store default cover resources in the filesystem"""
    defaul_covers: dict = [{'url': DEFAULT_URL_COVER_L, 'size': 'l'}, {'url': DEFAULT_URL_COVER_S, 'size': 's'}]
    for cover in defaul_covers:
        if not _cover_exists('default', 'cover', cover['size']):
            _store_cover('default', 'cover', cover['url'], cover['size'])


# ========= Platforms utils =========
def _exclude_platforms(platforms) -> list['str']:
    [platforms.remove(excluded) for excluded in user_config['exclude']['platforms'] if excluded in platforms]


def get_platforms() -> list[str]:
    """Gets all filesystem platforms
    
    Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
    Automatically exclude folders defined in user config.
    """
    try:
        platforms: list[str] = list(os.walk(HIGH_PRIO_STRUCTURE_PATH))[0][1] if os.path.exists(HIGH_PRIO_STRUCTURE_PATH) else list(os.walk(LIBRARY_BASE_PATH))[0][1]
    except IndexError:
        raise PlatformsNotFoundException
    try:
        _exclude_platforms(platforms)
    except (KeyError, TypeError):
        pass
    return platforms


# ========= Roms utils =========
def get_roms_structure(p_slug: str) -> tuple:
    return f"{HIGH_PRIO_STRUCTURE_PATH}/{p_slug}" if os.path.exists(HIGH_PRIO_STRUCTURE_PATH) else f"{LIBRARY_BASE_PATH}/{p_slug}/roms"


def get_rom_files(rom: str, roms_path: str) -> list[str]:
    rom_files: list = []
    for path, _, files in os.walk(f"{roms_path}/{rom}"):
        [rom_files.append(f"{Path(path, f)}".replace(f"{roms_path}/{rom}/", '')) for f in _exclude_files(files, 'multi')]
    return rom_files


def _exclude_files(files, type) -> list[str]:
    if type == 'single':
        try:
            excluded_extensions = user_config['exclude']['roms'][f'{type}_file']['extensions']
        except (TypeError, KeyError):
            excluded_extensions: list = []
        try:
            excluded_names = user_config['exclude']['roms'][f'{type}_file']['names']
        except (TypeError, KeyError):
            excluded_names: list = []
    elif type == 'multi':
        try:
            excluded_extensions = user_config['exclude']['roms'][f'{type}_file']['parts']['extensions']
        except (TypeError, KeyError):
            excluded_extensions: list = []
        try:
            excluded_names = user_config['exclude']['roms'][f'{type}_file']['parts']['names']
        except (TypeError, KeyError):
            excluded_names: list = []
    filtered_files: list = []
    for file in files:
        try:
            if file.split('.')[-1] in excluded_extensions or file in excluded_names:
                filtered_files.append(file)
        except TypeError:
            pass
    files = [f for f in files if f not in filtered_files]
    return files


def _exclude_multi_roms(roms) -> list[str]:
    try:
        excluded_names: list = []
        excluded_names = user_config['exclude']['roms']['multi_file']['names']
    except (TypeError, KeyError):
        pass
    filtered_files: list = []
    for rom in roms:
        try:
            if rom in excluded_names:
                filtered_files.append(rom)
        except TypeError:
            pass
    roms = [f for f in roms if f not in filtered_files]
    return roms


def get_rom_size(multi: bool, rom: str, files: list, roms_path:str) -> str:
    files: list = [f"{roms_path}/{rom}"] if not multi else [f"{roms_path}/{rom}/{file}" for file in files]
    total_size: int = 0
    for file in files:
        total_size += os.stat(file).st_size
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if total_size < 1024.0 or unit == 'PB': break
        total_size /= 1024.0
    return round(total_size, 2), unit


def get_roms(p_slug: str) -> list[dict] or int:
    """Gets all filesystem roms for a platform

    Args:
        p_slug: short name of the platform
    Returns: list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH.
    """
    roms_path = get_roms_structure(p_slug)
    try:
        fs_single_roms: list[str] = list(os.walk(roms_path))[0][2]
    except IndexError:
        raise RomsNotFoundException(p_slug)
    try:
        fs_multi_roms: list[str] = list(os.walk(roms_path))[0][1]
    except IndexError:
        raise RomsNotFoundException(p_slug)
    fs_roms: list[dict] = [{'multi': False, 'file_name': rom} for rom in _exclude_files(fs_single_roms, 'single')] + \
                          [{'multi': True, 'file_name': rom} for rom in _exclude_multi_roms(fs_multi_roms)]
    [rom.update({'files': get_rom_files(rom['file_name'], roms_path)}) for rom in fs_roms]
    return fs_roms


def _rom_exists(p_slug: str, file_name: str) -> bool:
    """Check if rom exists in filesystem
    
    Args:
        p_slug: short name of the platform
        file_name: rom file_name
    Returns
        True if rom exists in filesystem else False
    """
    rom_path = get_roms_structure(p_slug)
    exists: bool = True if os.path.exists(f"{rom_path}/{file_name}") else False
    return exists


def rename_rom(p_slug: str, old_name: str, new_name: str) -> None:
    if new_name != old_name:
        rom_path = get_roms_structure(p_slug)
        if _rom_exists(p_slug, new_name):
            raise RomAlreadyExistsException(new_name)
        os.rename(f"{rom_path}/{old_name}", f"{rom_path}/{new_name}")
    

def remove_rom(p_slug: str, file_name: str) -> None:
    rom_path = get_roms_structure(p_slug)
    try:
        try:
            os.remove(f"{rom_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{rom_path}/{file_name}")
    except FileNotFoundError:
        raise RomNotFoundError(file_name, p_slug)
