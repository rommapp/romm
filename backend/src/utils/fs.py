import os
import shutil
import re
from pathlib import Path

import requests
from fastapi import HTTPException

from config import user_config, LIBRARY_BASE_PATH, HIGH_PRIO_STRUCTURE_PATH, RESOURCES_BASE_PATH, DEFAULT_URL_COVER_L, DEFAULT_PATH_COVER_L, DEFAULT_URL_COVER_S, DEFAULT_PATH_COVER_S
from handler import dbh
from logger.logger import log


# ========= Defaults utils =========
def store_default_resources(overwrite: bool) -> None:
    """Store default no_cover resources in the filesystem
    
    Args:
        overwrite: flag to overwrite or not default resources
    """
    if overwrite or not _cover_exists('default', 'cover', 'l'):
        _store_cover('default', 'cover', DEFAULT_URL_COVER_L, 'l')
    if overwrite or not _cover_exists('default', 'cover', 's'):
        _store_cover('default', 'cover', DEFAULT_URL_COVER_S, 's')


# ========= Platforms utils =========
def get_platforms() -> list[str]:
    """Gets all filesystem platforms
    
    Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
    Automatically discards the reserved directories such resources or database directory.
    """
    try:
        if os.path.exists(f"{LIBRARY_BASE_PATH}/roms"):
            platforms: list[str] = list(os.walk(f"{LIBRARY_BASE_PATH}/roms"))[0][1]
        else:
            platforms: list[str] = list(os.walk(LIBRARY_BASE_PATH))[0][1]
        try:
            excluded_folders: list = user_config['exclude']['folders']
            try:
                [platforms.remove(excluded) for excluded in excluded_folders if excluded in platforms]
            except TypeError:
                pass
        except KeyError:
            pass
        log.info(f"filesystem platforms found: {platforms}")
        return platforms
    except IndexError:
        raise HTTPException(status_code=404, detail="Platforms not found.")


# ========= Roms utils =========
def _check_folder_structure(p_slug) -> tuple:
    roms_path: str = f"{HIGH_PRIO_STRUCTURE_PATH}/{p_slug}" if os.path.exists(HIGH_PRIO_STRUCTURE_PATH) else f"{LIBRARY_BASE_PATH}/{p_slug}/roms"
    try:
        roms_files = list(os.walk(roms_path))[0][2]
    except IndexError:
        roms_files = []
    return roms_path, roms_files
    

def _exclude_files(roms_files) -> list[str]:
    try:
        excluded_files: list = user_config['exclude']['files']
        filtered_files: list = []
        for file_name in roms_files:
            if file_name.split('.')[-1] in excluded_files:
                filtered_files.append(file_name)
        roms_files = [f for f in roms_files if f not in filtered_files]
    except (TypeError, KeyError):
        pass
    return roms_files


def parse_tags(file_name: str) -> tuple:
    reg=''
    rev=''
    other_tags=[]
    tags = re.findall('\(([^)]+)', file_name)
    for t in tags:
        if t.split('-')[0].lower() == 'reg':
            try: reg=t.split('-', 1)[1]
            except IndexError: pass
        elif t.split('-')[0].lower() == 'rev':
            try: rev=t.split('-', 1)[1]
            except IndexError: pass
        else:
            other_tags.append(t)
    return reg, rev, other_tags


def get_roms(p_slug: str, full_scan: bool, only_amount: bool = False) -> list[dict]:
    """Gets all filesystem roms for a platform

    Args:
        p_slug: short name of the platform
        only_amount: flag to return only amount of roms instead of all info
    Returns: list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH. Just the amount of them if only_amount=True
    """
    roms: list[dict] = []
    roms_path, roms_files = _check_folder_structure(p_slug)
    roms_files = _exclude_files(roms_files)

    if only_amount: return len(roms_files)

    excluded_roms: list[str] = [rom.file_name for rom in dbh.get_roms(p_slug)]
    for rom in roms_files:
        if rom in excluded_roms and not full_scan: continue
        file_size: str = str(round(os.stat(f"{roms_path}/{rom}").st_size / (1024 * 1024), 2))
        file_extension: str = rom.split('.')[-1] if '.' in rom else ""
        reg, rev, other_tags = parse_tags(rom)
        roms.append({'file_name': rom, 'file_path': roms_path, 'file_size': file_size, 'file_extension': file_extension,
                     'region': reg, 'revision': rev, 'tags': other_tags})
    log.info(f"Roms found for {p_slug}: {roms}")
    if only_amount: return 0
    return roms


def _rom_exists(p_slug: str, file_name: str) -> bool:
    """Check if rom exists in filesystem
    
    Args:
        p_slug: short name of the platform
        file_name: rom file_name
    Returns
        True if rom exists in filesystem else False
    """
    rom_path, _ = _check_folder_structure(p_slug)
    exists: bool = True if os.path.exists(f"{rom_path}/{file_name}") else False
    return exists


def rename_rom(p_slug: str, old_name: str, new_name: str) -> None:
    if new_name != old_name:
        rom_path, _ = _check_folder_structure(p_slug)
        if _rom_exists(p_slug, new_name): raise HTTPException(status_code=500, detail=f"Can't rename: {new_name} already exists.")
        os.rename(f"{rom_path}/{old_name}", f"{rom_path}/{new_name}")
    

def delete_rom(p_slug: str, file_name: str) -> None:
    try:
        rom_path, _ = _check_folder_structure(p_slug)
        os.remove(f"{rom_path}/{file_name}")
    except FileNotFoundError:
        log.warning(f"Rom not found in filesystem: {rom_path}/{file_name}")


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


def _get_cover_path(p_slug: str, file_name: str, size: str) -> str:
    """Returns rom cover filesystem path adapted to frontend folder structure
    
    Args:
        p_slug: short name of the platform
        file_name: name of rom file
        size: size of the cover -> big as 'l' | small as 's'
    """
    return f"/assets{RESOURCES_BASE_PATH}/{p_slug}/{file_name}_{size}.png"


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
        log.warning(f"{file_name} {sizes[size]} cover couldn't be downloaded")


def get_cover_details(overwrite: bool, p_slug: str, file_name: str, url_cover: str) -> tuple:
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
    return path_cover_s, path_cover_l, has_cover

