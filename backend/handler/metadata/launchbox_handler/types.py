import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from config import ROMM_BASE_PATH

from ..base_handler import BaseRom

LAUNCHBOX_PLATFORMS_KEY: Final[str] = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final[str] = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final[str] = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY: Final[str] = (
    "romm:launchbox_metadata_alternate_name"
)
LAUNCHBOX_METADATA_IMAGE_KEY: Final[str] = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final[str] = "romm:launchbox_mame"
LAUNCHBOX_FILES_KEY: Final[str] = "romm:launchbox_files"

LAUNCHBOX_LOCAL_DIR: Final[Path] = Path(ROMM_BASE_PATH) / "launchbox"
LAUNCHBOX_PLATFORMS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Data" / "Platforms"
LAUNCHBOX_IMAGES_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Images"
LAUNCHBOX_MANUALS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Manuals"
LAUNCHBOX_VIDEOS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Videos"

# Regex to detect LaunchBox ID tags in filenames like (launchbox-12345)
LAUNCHBOX_TAG_REGEX = re.compile(r"\(launchbox-(\d+)\)", re.IGNORECASE)
DASH_COLON_REGEX = re.compile(r"\s?-\s")


class LaunchboxImage(TypedDict):
    url: str
    type: NotRequired[str]
    region: NotRequired[str]


class LaunchboxPlatform(TypedDict):
    slug: str
    launchbox_id: int | None
    name: NotRequired[str]
    images: NotRequired[list[LaunchboxImage]]


class LaunchboxMetadata(TypedDict):
    first_release_date: int | None
    max_players: NotRequired[int]
    release_type: NotRequired[str]
    cooperative: NotRequired[bool]
    youtube_video_id: NotRequired[str]
    community_rating: NotRequired[float]
    community_rating_count: NotRequired[int]
    wikipedia_url: NotRequired[str]
    esrb: NotRequired[str]
    genres: NotRequired[list[str]]
    companies: NotRequired[list[str]]
    images: list[LaunchboxImage]
    video_url: NotRequired[str]
    video_path: NotRequired[str]


class LaunchboxRom(BaseRom):
    launchbox_id: int | None
    launchbox_metadata: NotRequired[LaunchboxMetadata]


class LocalMediaContext(TypedDict):
    base: Path
    stems: list[str]
    preferred_regions: list[str]


@dataclass(frozen=True, slots=True)
class MediaRequest:
    platform_name: str | None
    fs_name: str
    title: str
    region_hint: str | None
    remote_images: list[dict] | None
    remote_enabled: bool
