from dataclasses import dataclass

from config.config import DEFAULT_IMAGE_PATH


@dataclass
class Platform:
    igdb_id: str = ""
    sgdb_id: str = ""
    slug: str = ""
    name: str = ""
    path_logo: str = DEFAULT_IMAGE_PATH


@dataclass
class Rom:
    igdb_id: str = ""
    sgdb_id: str = ""
    platform_igdb_id: str = ""
    platform_sgdb_id: str = ""
    filename: str = ""
    name: str = ""
    path_cover: str = DEFAULT_IMAGE_PATH
