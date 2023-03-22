from dataclasses import dataclass

from config.config import DEFAULT_PATH_LOGO


@dataclass
class Platform:
    igdb_id: str = ""
    sgdb_id: str = ""
    slug: str = ""
    name: str = ""
    path_logo: str = DEFAULT_PATH_LOGO


@dataclass
class Rom:
    r_igdb_id: str = ""
    r_sgdb_id: str = ""
    p_igdb_id: str = ""
    p_sgdb_id: str = ""
    filename_no_ext: str = ""
    filename: str = ""
    name: str = ""
    r_slug: str = ""
    summary: str = ""
    p_slug: str = ""
    path_cover_l: str = ""
    path_cover_s: str = ""
    has_cover: int = 0
