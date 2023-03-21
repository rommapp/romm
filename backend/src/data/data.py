from dataclasses import dataclass

from config.config import DEFAULT_LOGO_PATH, DEFAULT_COVER_PATH_BIG, DEFAULT_COVER_PATH_SMALL


@dataclass
class Platform:
    igdb_id: str = ""
    sgdb_id: str = ""
    slug: str = ""
    name: str = ""
    path_logo: str = DEFAULT_LOGO_PATH


@dataclass
class Rom:
    igdb_id: str = ""
    sgdb_id: str = ""
    platform_igdb_id: str = ""
    platform_sgdb_id: str = ""
    filename_no_ext: str = ""
    filename: str = ""
    name: str = ""
    slug: str = ""
    summary: str = ""
    platform_slug: str = ""
    path_cover_big: str = DEFAULT_COVER_PATH_BIG
    path_cover_small: str = DEFAULT_COVER_PATH_SMALL
