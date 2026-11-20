from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final, NotRequired, TypedDict, get_type_hints

from fastapi import Request
from pydantic import (
    ConfigDict,
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from endpoints.responses.assets import (
    HIDDEN_ASSET_ANNOTATIONS,
    SaveSchema,
    ScreenshotSchema,
    StateSchema,
    UserSaveSchema,
    UserScreenshotSchema,
    UserStateSchema,
)
from endpoints.responses.snapshots import ChannelSchema, build_channel_schemas
from handler.metadata.csdb_handler import CsdbMetadata
from handler.metadata.demozoo_handler import DemozooMetadata
from handler.metadata.flashpoint_handler import FlashpointMetadata
from handler.metadata.gamelist_handler import GamelistMetadata
from handler.metadata.hasheous_handler import HasheousMetadata
from handler.metadata.hltb_handler import HLTBMetadata
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.launchbox_handler.types import LaunchboxMetadata
from handler.metadata.moby_handler import MobyMetadata
from handler.metadata.pouet_handler import PouetMetadata
from handler.metadata.ra_handler import RAMetadata
from handler.metadata.ss_handler import SSMetadata
from handler.metadata.steam_handler import SteamMetadata
from handler.scan.sources import SCAN_CLAIMS_KEY
from handler.snapshots.legacy import sync_file
from models.collection import Collection, SmartCollection
from models.rom import (
    PROVIDER_METADATA_COLUMNS,
    DocSource,
    Rom,
    RomArchiveMember,
    RomFile,
    RomFileCategory,
    RomNote,
    RomUserStatus,
    SaveTargetLayout,
)
from utils.conversion_cache import offered_download_formats
from utils.facets import facet_names
from utils.rom_patcher import is_patch_file_name

from .base import BaseModel, UTCDatetime

SORT_COMPARE_REGEX = re.compile(r"^([Tt]he|[Aa]|[Aa]nd)\s")


class UserNoteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    is_public: bool
    tags: list[str] | None = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
    user_id: int
    username: str
    # Author identity for rendering an avatar next to community notes.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None

    @classmethod
    def from_rom_note(cls, note: RomNote) -> UserNoteSchema:
        """Build the response for a note, taking its author off the joined `user`."""
        return cls(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=note.tags,
            created_at=note.created_at,
            updated_at=note.updated_at,
            user_id=note.user_id,
            username=note.user.username,
            user_avatar_path=note.user.avatar_path,
            user_updated_at=note.user.updated_at,
        )


RomIGDBMetadata = TypedDict(  # type: ignore[misc]
    "RomIGDBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(IGDBMetadata).items()},
    total=False,
)
RomMobyMetadata = TypedDict(  # type: ignore[misc]
    "RomMobyMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(MobyMetadata).items()},
    total=False,
)
RomSSMetadata = TypedDict(  # type: ignore[misc]
    "RomSSMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(SSMetadata).items()},
    total=False,
)
RomRAMetadata = TypedDict(  # type: ignore[misc]
    "RomRAMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(RAMetadata).items()},
    total=False,
)
RomLaunchboxMetadata = TypedDict(  # type: ignore[misc]
    "RomLaunchboxMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(LaunchboxMetadata).items()},
    total=False,
)
RomHasheousMetadata = TypedDict(  # type: ignore[misc]
    "RomHasheousMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(HasheousMetadata).items()},
    total=False,
)
RomFlashpointMetadata = TypedDict(  # type: ignore[misc]
    "RomFlashpointMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(FlashpointMetadata).items()},
    total=False,
)
RomHLTBMetadata = TypedDict(  # type: ignore[misc]
    "RomHLTBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(HLTBMetadata).items()},
    total=False,
)
RomDemozooMetadata = TypedDict(  # type: ignore[misc]
    "RomDemozooMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(DemozooMetadata).items()},
    total=False,
)
RomPouetMetadata = TypedDict(  # type: ignore[misc]
    "RomPouetMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(PouetMetadata).items()},
    total=False,
)
RomCsdbMetadata = TypedDict(  # type: ignore[misc]
    "RomCsdbMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(CsdbMetadata).items()},
    total=False,
)
RomSteamMetadata = TypedDict(  # type: ignore[misc]
    "RomSteamMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(SteamMetadata).items()},
    total=False,
)
RomGamelistMetadata = TypedDict(  # type: ignore[misc]
    "RomGamelistMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(GamelistMetadata).items()},
    total=False,
)
ManualMetadata = TypedDict(
    "ManualMetadata",
    {
        "genres": list[str] | None,
        "franchises": list[str] | None,
        "companies": list[str] | None,
        "publishers": list[str] | None,
        "developers": list[str] | None,
        "game_modes": list[str] | None,
        "age_ratings": list[str] | None,
        "first_release_date": int | None,
        "youtube_video_id": str | None,
        "alternative_names": list[str] | None,
    },
    total=False,
)


def _name_list_keys(metadata: type) -> frozenset[str]:
    return frozenset(
        key
        for key, hint in get_type_hints(metadata).items()
        if hint in (list[str], list[str] | None)
    )


_METADATA_NAME_LIST_KEYS: Final = {
    "igdb_metadata": _name_list_keys(RomIGDBMetadata),
    "moby_metadata": _name_list_keys(RomMobyMetadata),
    "ss_metadata": _name_list_keys(RomSSMetadata),
    "launchbox_metadata": _name_list_keys(RomLaunchboxMetadata),
    "hasheous_metadata": _name_list_keys(RomHasheousMetadata),
    "flashpoint_metadata": _name_list_keys(RomFlashpointMetadata),
    "hltb_metadata": _name_list_keys(RomHLTBMetadata),
    "demozoo_metadata": _name_list_keys(RomDemozooMetadata),
    "pouet_metadata": _name_list_keys(RomPouetMetadata),
    "csdb_metadata": _name_list_keys(RomCsdbMetadata),
    "steam_metadata": _name_list_keys(RomSteamMetadata),
    "gamelist_metadata": _name_list_keys(RomGamelistMetadata),
    "manual_metadata": _name_list_keys(ManualMetadata),
    "merged_ra_metadata": _name_list_keys(RomRAMetadata),
}


def clean_metadata_name_lists(
    field: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Run `facet_names` over the keys of a ROM `field`'s blob typed as a list of names."""
    keys = _METADATA_NAME_LIST_KEYS.get(field, frozenset())
    return {
        key: facet_names(value) if key in keys and value is not None else value
        for key, value in metadata.items()
        if key != SCAN_CLAIMS_KEY
    }


def rom_user_schema_factory() -> RomUserSchema:
    now = datetime.now(timezone.utc)
    return RomUserSchema(
        id=-1,
        user_id=-1,
        rom_id=-1,
        created_at=now,
        updated_at=now,
        last_played=None,
        is_main_sibling=False,
        backlogged=False,
        now_playing=False,
        hidden=False,
        rating=0,
        difficulty=0,
        completion=0,
        status=None,
        pinned_media=None,
    )


class RomUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    rom_id: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    last_played: UTCDatetime | None
    is_main_sibling: bool
    """Whether the user chose this version as the main one of its game."""
    backlogged: bool
    now_playing: bool
    hidden: bool
    rating: int
    """The user's rating, from 0 to 10. 0 means unset."""
    difficulty: int
    """The user's difficulty rating, from 0 to 10. 0 means unset."""
    completion: int
    """The user's completion percentage, from 0 to 100. 0 means unset."""
    status: RomUserStatus | None
    pinned_media: list[str] | None
    """The media keys pinned on the overview, in order. Null means the default selection."""

    @classmethod
    def for_user(cls, user_id: int, db_rom: Rom) -> RomUserSchema:
        for n in db_rom.rom_users:
            if n.user_id == user_id:
                return cls.model_validate(n)

        # Return a dummy RomUserSchema if the user + rom combination doesn't exist
        return rom_user_schema_factory()


class TrackMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    genre: str | None = None
    track: int | None = None
    disc: int | None = None
    duration_seconds: float | None = None
    has_embedded_cover: bool = False
    cover_path: str | None = None


class DocMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: DocSource
    source_url: str | None = None
    author: str | None = None
    title: str | None = None


class RomFileUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rom_file_id: int
    user_id: int
    progress: float
    last_page: int | None = None
    finished: bool = False
    last_read_at: UTCDatetime | None = None


class RomFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rom_id: int
    file_name: str
    """The file name, extension included."""
    file_path: str
    """The folder holding the file."""
    file_size_bytes: int
    full_path: str
    is_top_level: bool
    missing_from_fs: bool
    """True when the file is gone from disk."""
    created_at: UTCDatetime
    updated_at: UTCDatetime
    last_modified: UTCDatetime | None
    """When the file was last modified on disk."""
    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None
    ra_hash: str | None
    """The hash RetroAchievements uses to identify the file."""
    chd_sha1_hash: str | None
    archive_members: list[RomArchiveMember] | None
    category: RomFileCategory | None
    track_meta: TrackMetaSchema | None = None
    """The audio tags of a soundtrack file."""
    doc_meta: DocMetaSchema | None = None
    """The details of a manual or walkthrough file."""

    @model_validator(mode="after")
    def default_category_for_non_nested(self) -> RomFileSchema:
        # Rows scanned before patch formats were classified still carry their folder's.
        if is_patch_file_name(self.file_name):
            self.category = RomFileCategory.PATCH
        elif self.category is None and self.is_top_level:
            self.category = RomFileCategory.GAME
        return self


class SoundtrackTrackMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: int
    file_name: str
    file_size_bytes: int
    track_meta: TrackMetaSchema | None = None


class RomMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rom_id: int
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    """The game collections the title belongs to, merged from the matched providers."""
    companies: list[str]
    publishers: list[str]
    developers: list[str]
    game_modes: list[str]
    age_ratings: list[str]
    player_count: str
    first_release_date: int | None
    """The first release date, as a Unix timestamp in milliseconds."""
    average_rating: float | None
    """The average of the ratings the matched providers report."""

    @field_validator(
        "genres",
        "franchises",
        "collections",
        "companies",
        "publishers",
        "developers",
        "game_modes",
        mode="before",
    )
    def sort_names(cls, v: object) -> list[str]:
        return sorted(facet_names(v))

    @field_validator("age_ratings", mode="before")
    def normalize_age_ratings(cls, v: str | list[str] | None) -> list[str]:
        if not v:
            return []

        # MySQL/MariaDB returns a scalar string instead of a single-element array
        # when using JSON_EXTRACT with a [*] wildcard path on a single-element array.
        if isinstance(v, str):
            return sorted([v])

        return sorted(v)


class RomSchema(BaseModel):
    """One version of a game on one platform: a ROM file or folder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    igdb_id: int | None
    sgdb_id: int | None
    """The SteamGridDB game ID, used to find artwork."""
    moby_id: int | None
    ss_id: int | None
    ra_id: int | None
    launchbox_id: int | None
    hasheous_id: int | None
    tgdb_id: int | None
    flashpoint_id: str | None
    hltb_id: int | None
    demozoo_id: int | None
    """The Demozoo production ID, for demoscene releases."""
    pouet_id: int | None
    """The Pouët production ID, for demoscene releases."""
    csdb_id: int | None
    """The CSDb release ID, for Commodore 64 releases."""
    steam_id: int | None
    gamelist_id: str | None
    """A random ID generated for the ES-DE `gamelist.xml` entry when it was read."""
    libretro_id: str | None
    """The SHA-1 hash of the matched Libretro artwork's file name."""

    platform_id: int
    platform_slug: str
    platform_fs_slug: str
    """The name of the platform's folder in the library."""
    platform_custom_name: str | None
    platform_display_name: str
    """The custom name when set, otherwise the platform's own name."""

    fs_name: str
    """The file or folder name, extension included."""
    fs_name_no_tags: str
    """The name without its extension or any tags in parentheses or brackets. `Example Game (USA) (Rev 1).z64` becomes `Example Game`."""
    fs_name_no_ext: str
    """The name without its extension. Tags are kept, so the same file becomes `Example Game (USA) (Rev 1)`."""
    fs_extension: str
    """The file extension without the dot, such as `z64`. Empty for a folder."""
    fs_path: str
    """The folder holding the rom, relative to the library root."""
    fs_size_bytes: int
    """The total size of all the rom's files, in bytes."""

    name: str | None
    """The display name, from the matched metadata or the file name."""
    name_sort_key: str | None
    """The key used to sort by name: the name in lowercase, without a leading article. `The Old Game` becomes `old game`."""
    slug: str | None
    summary: str | None

    # Metadata fields
    alternative_names: list[str]
    """Other titles the game is known by, excluding the display name. If the user has set titles by hand, only those are used. Otherwise they come from IGDB, MobyGames and ScreenScraper."""
    youtube_video_id: str | None
    metadatum: RomMetadataSchema
    """The metadata merged from every matched provider, used for filtering and sorting."""
    igdb_metadata: RomIGDBMetadata | None
    """The raw IGDB metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    moby_metadata: RomMobyMetadata | None
    """The raw MobyGames metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    ss_metadata: RomSSMetadata | None
    """The raw ScreenScraper metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    launchbox_metadata: RomLaunchboxMetadata | None
    """The raw LaunchBox metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    hasheous_metadata: RomHasheousMetadata | None
    """The raw Hasheous metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    flashpoint_metadata: RomFlashpointMetadata | None
    """The raw Flashpoint Project metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    hltb_metadata: RomHLTBMetadata | None
    """The raw HowLongToBeat metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    demozoo_metadata: RomDemozooMetadata | None
    """The raw Demozoo metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    pouet_metadata: RomPouetMetadata | None
    """The raw Pouët metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    csdb_metadata: RomCsdbMetadata | None
    """The raw CSDb metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    steam_metadata: RomSteamMetadata | None
    """The raw Steam metadata. An empty object when there is no match, and null when `with_provider_metadata` is false."""
    gamelist_metadata: RomGamelistMetadata | None
    """The raw ES-DE `gamelist.xml` metadata. An empty object when there is no entry, and null when `with_provider_metadata` is false."""
    manual_metadata: ManualMetadata | None
    """The metadata the user entered by hand. It takes precedence over provider metadata in `metadatum`."""

    path_cover_small: str | None
    """The path to the small cover, with a cache-busting timestamp. Empty when there is no cover."""
    path_cover_large: str | None
    """The path to the large cover, with a cache-busting timestamp. Empty when there is no cover."""
    url_cover: str | None
    """The remote URL the cover was fetched from."""

    has_manual: bool
    has_soundtrack: bool
    path_manual: str | None
    url_manual: str | None
    """The remote URL the manual was fetched from."""

    path_video: str | None
    """The path to a video, taken from the ScreenScraper, ES-DE or LaunchBox metadata, in that order of preference."""

    is_identifying: bool = False
    """True while a scan is looking up metadata for the rom."""
    is_unidentified: bool
    """True when no provider has matched the rom."""
    is_identified: bool
    """True when at least one provider has matched the rom."""

    revision: str | None
    """The revision read from the file name tags."""
    version: str | None
    """The version read from the file name tags."""
    regions: list[str]
    """The regions read from the file name tags, such as `Europe`."""
    languages: list[str]
    """The languages read from the file name tags."""
    tags: list[str]
    """The other tags read from the file name."""

    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None
    ra_hash: str | None
    """The hash RetroAchievements uses to identify the rom. Empty if it has not been computed."""
    title_id: str | None
    """The platform's own ID for the game, read from the rom file and normalized, such as `SLUS-20152`."""
    save_target: str | None
    """The on-disk name an emulator gives the game's saves: a file stem, a folder or a nested path."""
    save_target_layout: SaveTargetLayout | None
    """How to read `save_target`: as a single folder, a single file, a folder prefix, a file prefix or a nested path."""

    has_simple_single_file: bool
    """True for a single file at the top level."""
    has_nested_single_file: bool
    """True for a folder holding exactly one top-level file."""
    has_multiple_files: bool
    """True when more than one file or folder sits at the top level."""
    is_easyrpg_game: bool
    """True for an RPG Maker 2000 or 2003 game: a folder containing an `rpg_rt.ldb` database."""
    has_jsdos_bundle: bool
    """True when the ROM is a `.jsdos` bundle, or a folder with one at its top level."""
    full_path: str
    """The path of the file or folder relative to the library root: `fs_path` joined with `fs_name`."""
    created_at: UTCDatetime
    updated_at: UTCDatetime
    missing_from_fs: bool
    """True when the file or folder is gone from disk. The record stays until the missing-roms cleanup runs."""
    is_physical: bool
    """True for a physical copy with no file."""
    has_file_on_disk: bool
    """Whether a readable file backs the rom. False for physical games and for roms whose file is missing."""
    upc: str | None
    """The barcode of a physical game, used to look up its title when no name is given."""
    has_notes: bool
    """Whether the current user can see a note on the rom."""

    rom_user: RomUserSchema
    """The current user's data for the rom, such as status and rating."""
    merged_screenshots: list[str]
    """The paths of the screenshots a scan downloaded from the metadata providers."""
    merged_ra_metadata: RomRAMetadata | None
    """The RetroAchievements metadata with its achievements sorted for display."""

    files: list[RomFileSchema] = Field(validation_alias="included_files")
    """The rom's files. Lists include them only when `with_files` is true."""
    sibling_roms: list[SiblingRomSchema] = Field(
        validation_alias="included_sibling_roms"
    )
    """The other versions of this game on the platform, excluding any the user cannot see."""

    # The filename parser stores "" when a name has no such tag.
    @field_validator("revision", "version")
    def empty_tag_to_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator(*_METADATA_NAME_LIST_KEYS, mode="before")
    def clean_name_lists(cls, v: object, info: ValidationInfo) -> object:
        # A stored blob can hold {id, name} objects where a list of names belongs.
        if not isinstance(v, Mapping):
            return v
        return clean_metadata_name_lists(info.field_name or "", v)

    @field_validator("files")
    def sort_files(cls, v: list[RomFileSchema]) -> list[RomFileSchema]:
        return sorted(v, key=lambda x: x.file_name)

    @field_validator("sibling_roms")
    def sort_sibling_roms(cls, v: list[SiblingRomSchema]) -> list[SiblingRomSchema]:
        return sorted(v, key=lambda x: x.sort_comparator)

    @classmethod
    def populate_properties(
        cls, db_rom: Rom, request: Request, has_notes: bool | None = None
    ) -> Rom:
        db_rom.rom_user = RomUserSchema.for_user(request.user.id, db_rom)  # type: ignore[attr-defined]
        # Callers that batched the flag pass it in and never load `Rom.notes`.
        db_rom.has_notes = (  # type: ignore[attr-defined]
            any(
                note.is_public or note.user_id == request.user.id
                for note in db_rom.notes
            )
            if has_notes is None
            else has_notes
        )
        return db_rom

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, _request: Request) -> RomSchema:
        return cls.model_validate(db_rom)

    @field_validator("alternative_names")
    def sort_alternative_names(cls, v: list[str]) -> list[str]:
        return sorted(v)


class SiblingRomSchema(BaseModel):
    id: int
    name: str | None
    fs_name_no_tags: str
    """The file name without its extension or any tags in parentheses or brackets."""
    fs_name_no_ext: str
    """The file name without its extension. Tags are kept."""
    is_main_sibling: bool
    """Whether the user chose this version as the main one."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sort_comparator(self) -> str:
        """The lowercase name the versions are sorted by."""
        return (
            SORT_COMPARE_REGEX.sub(
                "",
                self.name or self.fs_name_no_tags,
            )
            .strip()
            .lower()
        )

    @classmethod
    def from_rom(cls, rom: Rom, *, is_main_sibling: bool = False) -> SiblingRomSchema:
        return cls(
            id=rom.id,
            name=rom.name,
            fs_name_no_tags=rom.fs_name_no_tags,
            fs_name_no_ext=rom.fs_name_no_ext,
            is_main_sibling=is_main_sibling,
        )


def _visible_siblings(db_rom: Rom, request: Request) -> list[Rom]:
    """`db_rom.sibling_roms` minus any sibling hidden from the caller.

    Single-rom endpoints (detail / simple fallback) read siblings off the
    eager-loaded relationship, which bypasses the list query's hidden filter.
    """
    siblings = list(db_rom.sibling_roms)
    if not request.user.is_authenticated:
        return siblings

    # Local import: breaks the responses.rom <-> handler.auth.dependencies cycle.
    from handler.auth.dependencies import get_permissions

    perms = get_permissions(request)
    return [s for s in siblings if perms.can_see_rom(s)]


# The schema serves `ra_metadata` as `merged_ra_metadata`, with absolute badge paths.
PROVIDER_METADATA_FIELDS: Final = (
    *(c for c in PROVIDER_METADATA_COLUMNS if c != "ra_metadata"),
    "merged_ra_metadata",
)


class SimpleRomSchema(RomSchema):
    screenshot_path: str | None = None
    """An image of where the user left off: the screenshot of the latest save, or else the title screen, or else the first gameplay screenshot. Only set when `last_played` is true."""

    @classmethod
    def from_orm_with_request(
        cls,
        db_rom: Rom,
        request: Request,
        files: Sequence[RomFile] | None = None,
        siblings: Sequence[tuple[Rom, bool]] | None = None,
        screenshot_path: str | None = None,
        has_notes: bool | None = None,
        with_provider_metadata: bool = True,
    ) -> SimpleRomSchema:
        db_rom = cls.populate_properties(db_rom, request, has_notes=has_notes)
        db_rom.screenshot_path = screenshot_path  # type: ignore[attr-defined]

        # The list endpoint passes pre-fetched `files`/`siblings` (batched via
        # get_files_for_roms / get_siblings_for_roms, no per-row hydration).
        # Single-rom endpoints (e.g. `/{id}/simple`, loaded via the
        # `with_details` decorator) pass neither and fall back to the
        # eager-loaded relationships. `None` (not provided) is distinct from an
        # explicit empty list (e.g. the gallery list, which intentionally omits
        # files unless `with_files` is set).
        if files is None:
            files = db_rom.files
        if siblings is None:
            user_id = request.user.id
            siblings = [
                (
                    s,
                    any(
                        ru.user_id == user_id and ru.is_main_sibling
                        for ru in s.rom_users
                    ),
                )
                for s in _visible_siblings(db_rom, request)
            ]

        db_rom.included_files = list(files)  # type: ignore[attr-defined]
        db_rom.included_sibling_roms = [  # type: ignore[attr-defined]
            SiblingRomSchema.from_rom(s, is_main_sibling=is_main)
            for s, is_main in siblings
        ]
        schema = cls.model_validate(db_rom)
        if not with_provider_metadata:
            # Nulled on the schema, as `db_rom` is session-bound and would be flushed.
            schema = schema.model_copy(update=dict.fromkeys(PROVIDER_METADATA_FIELDS))
        return schema

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SimpleRomSchema:
        db_rom.rom_user = rom_user_schema_factory()  # type: ignore[attr-defined]
        db_rom.included_files = []  # type: ignore[attr-defined]
        db_rom.included_sibling_roms = []  # type: ignore[attr-defined]
        db_rom.has_notes = False  # type: ignore[attr-defined]
        db_rom.screenshot_path = None  # type: ignore[attr-defined]
        return cls.model_validate(db_rom)


class UserCollectionSchema(BaseModel):
    id: int
    name: str
    is_smart: bool = False

    @classmethod
    def for_user(
        cls, user_id: int, collections: list[Collection]
    ) -> list["UserCollectionSchema"]:
        return [
            UserCollectionSchema(
                id=c.id,
                name=c.name,
            )
            for c in collections
            if c.user_id == user_id or c.is_public
        ]

    @classmethod
    def from_smart_collections(
        cls, smart_collections: Sequence[SmartCollection]
    ) -> list["UserCollectionSchema"]:
        # Membership + visibility are already filtered at the SQL layer by
        # get_smart_collections_for_rom, so this is a plain mapping (see #3934).
        return [
            UserCollectionSchema(
                id=c.id,
                name=c.name,
                is_smart=True,
            )
            for c in smart_collections
        ]


class DetailedRomSchema(RomSchema):
    user_saves: list[SaveSchema]
    """The caller's own saves for the rom."""
    user_states: list[StateSchema]
    """The caller's own states for the rom."""
    all_user_saves: list[UserSaveSchema]
    """The caller's own saves and other users' public saves, each with its owner's name and avatar."""
    all_user_states: list[UserStateSchema]
    """The caller's own states and other users' public states, each with its owner's name and avatar."""
    user_channels: list[ChannelSchema]
    """The caller's sync channels for the rom, followed by other users' public channels."""
    channel_file_id: int | None
    """The ID of the file that a new channel for this rom is attached to."""
    snapshot_save_ids: list[int]
    """The IDs of the saves that belong to a channel. Any save not listed here was uploaded to a slot the legacy way."""
    user_screenshots: list[ScreenshotSchema]
    """The caller's own screenshots for the rom."""
    all_user_screenshots: list[UserScreenshotSchema]
    """The gallery screenshots the caller can see: their own and other users' public ones. Thumbnails captured with saves and states are not included."""
    user_collections: list[UserCollectionSchema]
    """The collections containing the rom that the caller can see, both their own and other users' public ones, including smart collections."""
    all_user_notes: list[UserNoteSchema]
    """The notes the caller can see, most recently updated first."""
    download_formats: list[str]
    """The formats the caller can request with `?format=` when downloading the rom's file. Only set for roms with a single file."""

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        user_id = request.user.id
        db_rom = cls.populate_properties(db_rom, request)

        sorted_siblings = sorted(
            (
                SiblingRomSchema.from_rom(
                    s,
                    is_main_sibling=any(
                        ru.user_id == user_id and ru.is_main_sibling
                        for ru in s.rom_users
                    ),
                )
                for s in _visible_siblings(db_rom, request)
            ),
            key=lambda x: x.sort_comparator,
        )
        db_rom.included_sibling_roms = sorted_siblings  # type: ignore[attr-defined]
        db_rom.included_files = sorted(db_rom.files, key=lambda x: x.file_name)  # type: ignore[attr-defined]
        db_rom.download_formats = offered_download_formats(  # type: ignore[attr-defined]
            db_rom.platform_slug, db_rom.files, request
        )

        db_rom.user_saves = [  # type: ignore[attr-defined]
            SaveSchema.model_validate(s) for s in db_rom.saves if s.user_id == user_id
        ]
        db_rom.user_states = [  # type: ignore[attr-defined]
            StateSchema.model_validate(s) for s in db_rom.states if s.user_id == user_id
        ]
        db_rom.user_screenshots = [  # type: ignore[attr-defined]
            ScreenshotSchema.model_validate(s)
            for s in db_rom.screenshots
            if s.user_id == user_id
        ]
        from handler.database import db_collection_handler

        # Standard collections come off the already-loaded join relationship;
        # smart collections have no reverse join, so match them by their cached
        # rom-id membership at the SQL layer (see #3934).
        db_rom.user_collections = [  # type: ignore[attr-defined]
            *UserCollectionSchema.for_user(user_id, db_rom.collections),
            *UserCollectionSchema.from_smart_collections(
                db_collection_handler.get_smart_collections_for_rom(
                    rom_id=db_rom.id, user_id=user_id
                )
            ),
        ]

        # Load notes separately using the database handler to avoid lazy loading issues
        from handler.database import db_rom_handler

        notes = db_rom_handler.get_rom_notes(rom_id=db_rom.id, user_id=user_id)

        all_notes = [UserNoteSchema.from_rom_note(note) for note in notes]

        # Sort notes by updated_at (most recent first)
        all_notes.sort(key=lambda x: x.updated_at, reverse=True)
        db_rom.all_user_notes = all_notes  # type: ignore[attr-defined]

        # Gallery screenshots visible to this user: own (public + private) plus
        # other users' public ones. Mirrors the notes flow above. Excludes the
        # auto-captured save/state thumbnails (is_gallery == False).
        from handler.database import db_screenshot_handler

        gallery_screenshots = db_screenshot_handler.get_rom_gallery_screenshots(
            rom_id=db_rom.id, user_id=user_id
        )
        db_rom.all_user_screenshots = [  # type: ignore[attr-defined]
            UserScreenshotSchema.model_validate(
                {
                    **{
                        field: getattr(s, field)
                        for field in ScreenshotSchema.model_fields
                    },
                    "username": s.user.username,
                    "user_avatar_path": s.user.avatar_path,
                    "user_updated_at": s.user.updated_at,
                }
            )
            for s in gallery_screenshots
        ]

        # Saves/states visible to this user: own (public + private) plus other
        # users' public ones. Mirrors the screenshots flow above.
        from handler.database import db_save_handler, db_state_handler

        # SaveSchema.model_validate handles the lazy `device_syncs` relationship
        # (skips it when unloaded); reuse it rather than getattr-ing raw fields.
        shared_saves = db_save_handler.get_rom_shared_saves(
            rom_id=db_rom.id, user_id=user_id
        )
        db_rom.all_user_saves = [  # type: ignore[attr-defined]
            UserSaveSchema.model_validate(
                {
                    **SaveSchema.model_validate(s).model_dump(),
                    **({} if s.user_id == user_id else HIDDEN_ASSET_ANNOTATIONS),
                    "username": s.user.username,
                    "user_avatar_path": s.user.avatar_path,
                    "user_updated_at": s.user.updated_at,
                }
            )
            for s in shared_saves
        ]

        shared_states = db_state_handler.get_rom_shared_states(
            rom_id=db_rom.id, user_id=user_id
        )
        db_rom.all_user_states = [  # type: ignore[attr-defined]
            UserStateSchema.model_validate(
                {
                    **StateSchema.model_validate(s).model_dump(),
                    **({} if s.user_id == user_id else HIDDEN_ASSET_ANNOTATIONS),
                    "username": s.user.username,
                    "user_avatar_path": s.user.avatar_path,
                    "user_updated_at": s.user.updated_at,
                }
            )
            for s in shared_states
        ]

        from handler.database import db_snapshot_handler

        db_rom.user_channels = build_channel_schemas(  # type: ignore[attr-defined]
            db_snapshot_handler.get_channels_for_rom(db_rom.id, user_id), request.user
        )
        channel_file = sync_file(db_rom.files)
        db_rom.channel_file_id = channel_file.id if channel_file else None  # type: ignore[attr-defined]
        db_rom.snapshot_save_ids = sorted(  # type: ignore[attr-defined]
            db_snapshot_handler.get_held_save_ids(
                [save.id for save in db_rom.user_saves]  # type: ignore[attr-defined]
            )
        )

        return cls.model_validate(db_rom)

    @field_validator("user_saves")
    def sort_user_saves(cls, v: list[SaveSchema]) -> list[SaveSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_states")
    def sort_user_states(cls, v: list[StateSchema]) -> list[StateSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_screenshots")
    def sort_user_screenshots(cls, v: list[ScreenshotSchema]) -> list[ScreenshotSchema]:
        return sorted(v, key=lambda x: x.created_at, reverse=True)
