import os
import re
import uuid
from collections.abc import Callable, Collection, Iterator
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict
from xml.etree.ElementTree import Element  # trunk-ignore(bandit/B405)

import pydash
from defusedxml import ElementTree as ET

from config.config_manager import PLATFORM_MEDIA_DIRS, MetadataMediaType
from config.config_manager import config_manager as cm
from handler.filesystem import fs_platform_handler, fs_resource_handler
from handler.filesystem.base_handler import (
    normalize_provider_languages,
    normalize_provider_regions,
)
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, compute_name_sort_key
from utils.filesystem import join_rel_path, rel_platform_folder

from .base_handler import BaseRom, MetadataHandler

# https://github.com/Aloshi/EmulationStation/blob/master/GAMELISTS.md#reference

# ES-DE writes a top-level <alternativeEmulator> sibling to <gameList>, which produces
# invalid multi-root XML. These patterns strip both self-closing and paired forms so the
# remaining document can be parsed.
ALTERNATIVE_EMULATOR_SELF_CLOSING_RE: Final = re.compile(
    r"<alternativeEmulator\b[^>]*/>"
)
ALTERNATIVE_EMULATOR_PAIRED_RE: Final = re.compile(
    r"<alternativeEmulator\b[^>]*>.*?</alternativeEmulator>",
    re.DOTALL,
)


def get_preferred_media_types() -> list[MetadataMediaType]:
    """Get preferred media types from config"""
    config = cm.get_config()
    return [MetadataMediaType(media) for media in config.SCAN_MEDIA]


class GamelistMetadataMedia(TypedDict):
    box2d_url: str | None
    box2d_back_url: str | None
    box3d_url: str | None
    fanart_url: str | None
    image_url: str | None
    manual_url: str | None
    marquee_url: str | None
    miximage_url: str | None
    miximage_v2_url: str | None
    physical_url: str | None
    screenshot_url: str | None
    thumbnail_url: str | None
    title_screen_url: str | None
    video_url: str | None


class GamelistMetadata(GamelistMetadataMedia):
    rating: float | None
    first_release_date: str | None
    sort_name: str | None
    companies: list[str] | None
    publishers: list[str] | None
    developers: list[str] | None
    franchises: list[str] | None
    genres: list[str] | None
    player_count: str | None
    md5_hash: str | None
    box2d_back_path: str | None
    box3d_path: str | None
    fanart_path: str | None
    miximage_path: str | None
    miximage_v2_path: str | None
    physical_path: str | None
    marquee_path: str | None
    title_screen_path: str | None
    video_path: str | None


class GamelistRom(BaseRom):
    gamelist_id: str | None
    regions: NotRequired[list[str]]
    languages: NotRequired[list[str]]
    gamelist_metadata: NotRequired[GamelistMetadata]


MediaUrlKey = Literal[
    "box2d_url",
    "box2d_back_url",
    "box3d_url",
    "fanart_url",
    "image_url",
    "manual_url",
    "marquee_url",
    "miximage_url",
    "miximage_v2_url",
    "physical_url",
    "screenshot_url",
    "thumbnail_url",
    "title_screen_url",
    "video_url",
]

MediaPathKey = Literal[
    "box2d_back_path",
    "box3d_path",
    "fanart_path",
    "miximage_path",
    "miximage_v2_path",
    "physical_path",
    "marquee_path",
    "title_screen_path",
    "video_path",
]

ESDE_MEDIA_MAP: Final[dict[MediaUrlKey, str]] = {
    "image_url": PLATFORM_MEDIA_DIRS["image"],
    "box2d_url": PLATFORM_MEDIA_DIRS["box2d"],
    "box2d_back_url": PLATFORM_MEDIA_DIRS["box2d_back"],
    "box3d_url": PLATFORM_MEDIA_DIRS["box3d"],
    "fanart_url": PLATFORM_MEDIA_DIRS["fanart"],
    "manual_url": PLATFORM_MEDIA_DIRS["manual"],
    "marquee_url": PLATFORM_MEDIA_DIRS["marquee"],
    "miximage_url": PLATFORM_MEDIA_DIRS["miximage"],
    "miximage_v2_url": PLATFORM_MEDIA_DIRS["miximage_v2"],
    "physical_url": PLATFORM_MEDIA_DIRS["physical"],
    "screenshot_url": PLATFORM_MEDIA_DIRS["screenshot"],
    "title_screen_url": PLATFORM_MEDIA_DIRS["title_screen"],
    "thumbnail_url": PLATFORM_MEDIA_DIRS["thumbnail"],
    "video_url": PLATFORM_MEDIA_DIRS["video"],
}

XML_TAG_MAP: Final[dict[MediaUrlKey, str]] = {
    "image_url": "image",
    "box2d_url": "cover",
    "box2d_back_url": "backcover",
    "box3d_url": "box3d",
    "fanart_url": "fanart",
    "manual_url": "manual",
    "marquee_url": "marquee",
    "miximage_url": "miximage",
    "miximage_v2_url": "miximage_v2",
    "physical_url": "physicalmedia",
    "screenshot_url": "screenshot",
    "title_screen_url": "title_screen",
    "thumbnail_url": "thumbnail",
    "video_url": "video",
}


def gamelist_path_to_filename(raw_path: str) -> str:
    """Return the filename a gamelist <path> refers to, without the `./` prefix."""
    return os.path.basename(raw_path.removeprefix("./"))


def gamelist_path_to_rel_path(raw_path: str) -> str:
    """Return a gamelist <path> as a path relative to the gamelist file itself.

    Unlike the filename alone, this tells two identically named roms in different
    folders apart, which a custom library structure allows.
    """
    return raw_path.removeprefix("./").strip("/")


PathValidator = Callable[[str], Path]


def _make_file_uri(
    platform_dir: str, raw_text: str, validate_path: PathValidator
) -> str:
    cleaned_text = raw_text.replace("./", "")
    joined_path = Path(platform_dir, cleaned_text)
    validate_path(str(joined_path))
    return f"file://{joined_path.as_posix()}"


def _split_comma_separated_values(value: str | None) -> list[str]:
    """Split comma separated values into clean list"""

    if not value:
        return []

    split_values = value.split(",")

    return pydash.compact([item.strip() for item in split_values])


MediaFileIndex = dict[MediaUrlKey, dict[str, str]]

# The order ES-DE probes extensions in when a ROM has media in several formats
ESDE_MEDIA_EXTENSION_PRIORITY: Final = (
    ".png",
    ".jpg",
    ".webp",
    ".mp4",
    ".mkv",
    ".avi",
    ".wmv",
    ".mov",
    ".webm",
    ".m4v",
    ".pdf",
)


_ESDE_MEDIA_EXTENSION_RANK: Final = {
    extension: rank for rank, extension in enumerate(ESDE_MEDIA_EXTENSION_PRIORITY)
}


def _esde_media_rank(file_name: str) -> tuple[int, str]:
    extension = os.path.splitext(file_name)[1].lower()
    return (
        _ESDE_MEDIA_EXTENSION_RANK.get(extension, len(_ESDE_MEDIA_EXTENSION_RANK)),
        file_name,
    )


def build_media_file_index(platform: Platform) -> MediaFileIndex:
    """Index each ES-DE media folder's files by stem, listing each folder once.

    Returns:
        The stem-to-URI mapping for every ESDE_MEDIA_MAP key.
    """
    platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)
    index: MediaFileIndex = {}

    for media_key, folder_name in ESDE_MEDIA_MAP.items():
        # Media is only a fallback, so an unusable folder must not fail the parse
        try:
            folder = fs_platform_handler.validate_path(
                os.path.join(platform_dir, folder_name)
            )
            uri_prefix = f"file://{folder.relative_to(fs_platform_handler.base_path)}"
            with os.scandir(folder) as it:
                file_names = sorted(
                    (entry.name for entry in it if entry.is_file()),
                    key=_esde_media_rank,
                )
        except (OSError, ValueError):
            file_names = []

        stems: dict[str, str] = {}
        for file_name in file_names:
            stems.setdefault(
                os.path.splitext(file_name)[0], f"{uri_prefix}/{file_name}"
            )
        index[media_key] = stems

    return index


def extract_media_from_gamelist_rom(
    game: Element,
    platform: Platform,
    media_files: MediaFileIndex,
    validate_path: PathValidator | None = None,
) -> GamelistMetadataMedia:
    platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)
    validate_path = validate_path or fs_platform_handler.validate_path

    gamelist_media = GamelistMetadataMedia(
        box2d_url=None,
        box2d_back_url=None,
        box3d_url=None,
        fanart_url=None,
        image_url=None,
        manual_url=None,
        marquee_url=None,
        miximage_url=None,
        miximage_v2_url=None,
        physical_url=None,
        screenshot_url=None,
        title_screen_url=None,
        thumbnail_url=None,
        video_url=None,
    )

    # Check explicit XML elements defined in gamelist.xml
    for media_key, xml_tag in XML_TAG_MAP.items():
        elem = game.find(xml_tag)
        if elem is not None and elem.text:
            try:
                gamelist_media[media_key] = _make_file_uri(
                    platform_dir, elem.text, validate_path
                )
            except ValueError as e:
                log.debug(f"Skipping gamelist <{xml_tag}> outside the library: {e}")

    # Fallback to the media folders' files named after the ROM
    path_elem = game.find("path")
    if path_elem is not None and path_elem.text:
        rom_name = os.path.basename(path_elem.text)
        rom_stem = os.path.splitext(rom_name)[0]
        is_directory: bool | None = None

        for media_key in ESDE_MEDIA_MAP:
            if gamelist_media[media_key]:
                continue

            files = media_files[media_key]
            if rom_name in files and rom_stem in files:
                # ES-DE names a directory's media after its full name, a file's
                # after its stem, so only a name both could match needs the disk.
                if is_directory is None:
                    is_directory = _is_directory_entry(
                        game, platform_dir, path_elem.text, validate_path
                    )
                name = rom_name if is_directory else rom_stem
            else:
                name = rom_name if rom_name in files else rom_stem
            gamelist_media[media_key] = files.get(name)

    return gamelist_media


def _is_directory_entry(
    game: Element, platform_dir: str, raw_path: str, validate_path: PathValidator
) -> bool:
    """Whether a gamelist entry names a directory rather than a file."""
    if game.tag == "folder":
        return True
    try:
        return validate_path(
            os.path.join(platform_dir, gamelist_path_to_rel_path(raw_path))
        ).is_dir()
    except ValueError:
        return False


def extract_metadata_from_gamelist_rom(
    game: Element,
    platform: Platform,
    media_files: MediaFileIndex,
    validate_path: PathValidator | None = None,
) -> GamelistMetadata:
    rating_elem = game.find("rating")
    releasedate_elem = game.find("releasedate")
    sortname_elem = game.find("sortname")
    developer_elem = game.find("developer")
    publisher_elem = game.find("publisher")
    family_elem = game.find("family")
    genre_elem = game.find("genre")
    players_elem = game.find("players")
    md5_elem = game.find("md5")

    rating = (
        float(rating_elem.text)
        if rating_elem is not None and rating_elem.text
        else None
    )
    first_release_date = (
        releasedate_elem.text
        if releasedate_elem is not None and releasedate_elem.text
        else None
    )
    sort_name = (
        sortname_elem.text if sortname_elem is not None and sortname_elem.text else None
    )
    developer = (
        developer_elem.text
        if developer_elem is not None and developer_elem.text
        else None
    )
    publisher = (
        publisher_elem.text
        if publisher_elem is not None and publisher_elem.text
        else None
    )
    family = family_elem.text if family_elem is not None and family_elem.text else None
    genre = genre_elem.text if genre_elem is not None and genre_elem.text else None
    players = (
        players_elem.text if players_elem is not None and players_elem.text else None
    )
    md5 = md5_elem.text if md5_elem is not None and md5_elem.text else None

    publishers = _split_comma_separated_values(publisher)
    developers = _split_comma_separated_values(developer)

    return GamelistMetadata(
        rating=rating,
        first_release_date=first_release_date,
        sort_name=sort_name,
        companies=list(dict.fromkeys([*developers, *publishers])),
        publishers=publishers,
        developers=developers,
        franchises=_split_comma_separated_values(family),
        genres=_split_comma_separated_values(genre),
        player_count=players,
        md5_hash=md5,
        box2d_back_path=None,
        box3d_path=None,
        fanart_path=None,
        miximage_path=None,
        miximage_v2_path=None,
        physical_path=None,
        marquee_path=None,
        title_screen_path=None,
        video_path=None,
        **extract_media_from_gamelist_rom(game, platform, media_files, validate_path),
    )


def populate_rom_specific_paths(
    rom_metadata: GamelistMetadata, rom: Rom
) -> dict[MediaPathKey, str]:
    """Populate ROM-specific paths after retrieving metadata from cache"""
    preferred_media_types = get_preferred_media_types()

    # Create a copy of the metadata to avoid modifying the cached version
    updated_metadata: dict[MediaPathKey, str] = {}

    # Set paths for media types that are preferred
    if MetadataMediaType.BOX2D_BACK in preferred_media_types and rom_metadata.get(
        "box2d_back_url"
    ):
        updated_metadata["box2d_back_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BOX2D_BACK)}/box2d_back.png"
        )
    if MetadataMediaType.BOX3D in preferred_media_types and rom_metadata.get(
        "box3d_url"
    ):
        updated_metadata["box3d_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BOX3D)}/box3d.png"
        )
    if MetadataMediaType.FANART in preferred_media_types and rom_metadata.get(
        "fanart_url"
    ):
        updated_metadata["fanart_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.FANART)}/fanart.png"
        )
    if MetadataMediaType.MARQUEE in preferred_media_types and rom_metadata.get(
        "marquee_url"
    ):
        updated_metadata["marquee_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MARQUEE)}/marquee.png"
        )
    if MetadataMediaType.MIXIMAGE in preferred_media_types and rom_metadata.get(
        "miximage_url"
    ):
        updated_metadata["miximage_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MIXIMAGE)}/miximage.png"
        )
    if MetadataMediaType.MIXIMAGE_V2 in preferred_media_types and rom_metadata.get(
        "miximage_v2_url"
    ):
        updated_metadata["miximage_v2_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MIXIMAGE_V2)}/miximage_v2.png"
        )
    if MetadataMediaType.PHYSICAL in preferred_media_types and rom_metadata.get(
        "physical_url"
    ):
        updated_metadata["physical_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.PHYSICAL)}/physical.png"
        )
    if MetadataMediaType.TITLE_SCREEN in preferred_media_types and rom_metadata.get(
        "title_screen_url"
    ):
        updated_metadata["title_screen_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.TITLE_SCREEN)}/title_screen.png"
        )
    if MetadataMediaType.VIDEO in preferred_media_types and rom_metadata.get(
        "video_url"
    ):
        updated_metadata["video_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.VIDEO)}/video.mp4"
        )

    return updated_metadata


class GamelistHandler(MetadataHandler):
    """Handler for ES-DE gamelist.xml metadata source"""

    def __init__(self) -> None:
        # Cache for storing parsed gamelist data by platform ID
        self._gamelist_cache: dict[int, dict[str, GamelistRom]] = {}
        # The file names a platform's cached entries were limited to, absent when complete
        self._gamelist_cache_scope: dict[int, frozenset[str]] = {}

    async def populate_cache(
        self, platform: Platform, fs_names: Collection[str] | None = None
    ) -> None:
        """Parse a platform's gamelist.xml ahead of the scan's lookups.

        Args:
            fs_names: Limits the parse to the entries for these file names, since
                resolving every entry's media is what makes a large gamelist slow.
        """
        if not self.is_enabled():
            return

        # Find the gamelist.xml file for this platform
        gamelist_file_path = await self._find_gamelist_file(platform)
        if not gamelist_file_path:
            return

        self._parse_gamelist_xml(
            gamelist_file_path,
            platform,
            fs_names=frozenset(fs_names) if fs_names is not None else None,
        )

    def clear_cache(self) -> None:
        """Clear the gamelist cache"""
        self._gamelist_cache.clear()
        self._gamelist_cache_scope.clear()

    def _cache_covers(self, platform_id: int, fs_names: frozenset[str] | None) -> bool:
        """Whether the platform's cached entries include every one for `fs_names`.

        Args:
            fs_names: The file names needed, or None for the whole gamelist.
        """
        if platform_id not in self._gamelist_cache:
            return False
        scope = self._gamelist_cache_scope.get(platform_id)
        return scope is None or (fs_names is not None and fs_names <= scope)

    @classmethod
    def is_enabled(cls) -> bool:
        return True

    async def heartbeat(self) -> bool:
        return True

    async def _find_gamelist_file(self, platform: Platform) -> Path | None:
        """Find the gamelist.xml file for a platform"""
        platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)

        # Check for platform-level gamelist.xml
        platform_gamelist = f"{platform_dir}/gamelist.xml"
        if await fs_platform_handler.file_exists(platform_gamelist):
            return fs_platform_handler.validate_path(platform_gamelist)

        return None

    def _iter_game_elements(self, gamelist_path: Path) -> Iterator[Element]:
        """Yield each top-level game/folder element of a gamelist.xml.

        Parsing incrementally keeps one entry alive at a time instead of
        holding a tree for the whole document, which matters on platforms
        with thousands of games.

        ES-DE writes an <alternativeEmulator> sibling to <gameList>, producing
        invalid multi-root XML that the incremental parser rejects. Those files
        fall back to stripping the element from the document first. Entries are
        keyed by filename by the caller, so re-yielding any element already
        consumed before the failure is harmless.
        """
        try:
            for _, elem in ET.iterparse(gamelist_path, events=("end",)):
                if elem.tag in ("game", "folder"):
                    yield elem
                    elem.clear()
            return
        except ET.ParseError:
            pass

        xml_content = gamelist_path.read_text(encoding="utf-8", errors="replace")
        xml_content = ALTERNATIVE_EMULATOR_SELF_CLOSING_RE.sub("", xml_content)
        xml_content = ALTERNATIVE_EMULATOR_PAIRED_RE.sub("", xml_content)
        for elem in ET.fromstring(xml_content):
            if elem.tag in ("game", "folder"):
                yield elem

    def _parse_gamelist_xml(
        self,
        gamelist_path: Path,
        platform: Platform,
        fs_names: frozenset[str] | None = None,
    ) -> dict[str, GamelistRom]:
        """Parse a gamelist.xml file and return ROM data indexed by <path>.

        Entries are keyed by their path relative to the gamelist itself, so two
        identically named roms in different folders keep their own metadata. A bare
        file name stays a fallback key, since that is all some tools write.
        Results are cached by platform ID  to avoid re-parsing the same file multiple times.

        Args:
            fs_names: Limits the result to the entries for these file names.
        """
        cache_key = platform.id
        if self._cache_covers(cache_key, fs_names):
            log.debug(f"Using cached gamelist data for platform {platform.id}")
            return self._gamelist_cache[cache_key]

        # A limited cache is widened by reading only the names it lacks
        wanted = fs_names
        cached_scope = self._gamelist_cache_scope.get(cache_key)
        widened_from: dict[str, GamelistRom] | None = None
        if (
            fs_names is not None
            and cached_scope is not None
            and cache_key in self._gamelist_cache
        ):
            wanted = fs_names - cached_scope
            widened_from = self._gamelist_cache[cache_key]

        preferred_media_types = get_preferred_media_types()
        roms_data: dict[str, GamelistRom] = {}
        by_filename: dict[str, GamelistRom] = {}
        ambiguous_filenames: set[str] = set()

        try:
            media_files = build_media_file_index(platform)
            validate_path = fs_platform_handler.cached_path_validator()
            for game in self._iter_game_elements(gamelist_path):
                if game.tag not in ("game", "folder"):
                    continue

                path_elem = game.find("path")
                if path_elem is None or path_elem.text is None:
                    continue

                rel_path = gamelist_path_to_rel_path(path_elem.text)
                if wanted is not None and os.path.basename(rel_path) not in wanted:
                    continue
                filename = gamelist_path_to_filename(path_elem.text)

                # Extract metadata
                name_elem = game.find("name")
                desc_elem = game.find("desc")
                lang_elem = game.find("lang")
                region_elem = game.find("region")
                sortname_elem = game.find("sortname")

                name = (
                    name_elem.text if name_elem is not None and name_elem.text else ""
                )
                sort_name = (
                    sortname_elem.text
                    if sortname_elem is not None and sortname_elem.text
                    else None
                )
                summary = (
                    desc_elem.text if desc_elem is not None and desc_elem.text else ""
                )
                regions = normalize_provider_regions(
                    _split_comma_separated_values(
                        region_elem.text if region_elem is not None else None
                    )
                )
                languages = normalize_provider_languages(
                    _split_comma_separated_values(
                        lang_elem.text if lang_elem is not None else None
                    )
                )

                # Build ROM data
                rom_metadata = extract_metadata_from_gamelist_rom(
                    game, platform, media_files, validate_path
                )
                name_sort_key = compute_name_sort_key(sort_name) if sort_name else None
                rom_data = GamelistRom(
                    gamelist_id=str(uuid.uuid4()),
                    name=name,
                    name_sort_key=name_sort_key,
                    summary=summary,
                    regions=regions,
                    languages=languages,
                    gamelist_metadata=rom_metadata,
                )

                # Choose which cover style to use
                cover_url = rom_metadata["box2d_url"] or rom_metadata["image_url"]
                if cover_url:
                    rom_data["url_cover"] = cover_url

                # Grab the manual
                manual_url = rom_metadata["manual_url"]
                if manual_url and MetadataMediaType.MANUAL in preferred_media_types:
                    rom_data["url_manual"] = manual_url

                # Build list of screenshot URLs. The title screen is stored in
                # its own media folder via title_screen_path, so it must not
                # also land in screenshots/.
                url_screenshots = []
                if (
                    rom_metadata["screenshot_url"]
                    and MetadataMediaType.SCREENSHOT in preferred_media_types
                ):
                    url_screenshots.append(rom_metadata["screenshot_url"])
                rom_data["url_screenshots"] = url_screenshots

                roms_data[rel_path] = rom_data
                if filename in by_filename:
                    ambiguous_filenames.add(filename)
                by_filename[filename] = rom_data

            for name, data in by_filename.items():
                if name not in ambiguous_filenames:
                    roms_data.setdefault(name, data)

            # Cache the parsed data for this platform
            if widened_from is not None:
                roms_data = {**widened_from, **roms_data}
            self._gamelist_cache[cache_key] = roms_data
            if fs_names is None:
                self._gamelist_cache_scope.pop(cache_key, None)
            else:
                self._gamelist_cache_scope[cache_key] = fs_names | (
                    cached_scope or set()
                )
        except ET.ParseError as e:
            log.warning(f"Failed to parse gamelist.xml at {gamelist_path}: {e}")
            # Entries read before the document turned out to be invalid are
            # dropped, so a corrupt file yields nothing rather than a partial
            # import that silently looks complete.
            roms_data.clear()
        except Exception as e:
            log.error(f"Error reading gamelist.xml at {gamelist_path}: {e}")

        return roms_data

    async def get_rom(self, fs_name: str, platform: Platform, rom: Rom) -> GamelistRom:
        """Get ROM metadata from gamelist.xml files"""
        if not self.is_enabled():
            return GamelistRom(gamelist_id=None)

        # Find the gamelist.xml file for this platform
        gamelist_file_path = await self._find_gamelist_file(platform)
        if not gamelist_file_path:
            return GamelistRom(gamelist_id=None)

        # A cache limited to other file names is widened to this one
        is_limited = platform.id in self._gamelist_cache_scope
        all_roms_data = self._parse_gamelist_xml(
            gamelist_file_path,
            platform,
            fs_names=frozenset({fs_name}) if is_limited else None,
        )

        # The rom's own path wins over its bare file name, which a custom library
        # structure can leave shared with a rom in another folder.
        rel_path = join_rel_path(
            rel_platform_folder(
                rom.fs_path or "",
                fs_platform_handler.get_platform_fs_structure(platform.fs_slug),
            ),
            fs_name,
        )
        matched_key = next(
            (key for key in (rel_path, fs_name) if key in all_roms_data), None
        )
        if matched_key is not None:
            log.debug(f"Found exact gamelist match for {matched_key}")
            matched_rom = pydash.clone_deep(all_roms_data[matched_key])
            gamelist_metadata = matched_rom.get("gamelist_metadata")

            # Populate ROM-specific paths using the actual rom object
            if gamelist_metadata:
                rom_specific_paths = populate_rom_specific_paths(gamelist_metadata, rom)
                for path_key, path in rom_specific_paths.items():
                    gamelist_metadata[path_key] = path
                matched_rom["gamelist_metadata"] = gamelist_metadata

            return matched_rom

        return GamelistRom(gamelist_id=None)
