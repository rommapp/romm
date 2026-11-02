import asyncio
from collections.abc import Callable, Mapping
from typing import Any, Final, NotRequired, TypedDict

import socketio

from config.config_manager import config_manager as cm
from endpoints.responses.rom import SimpleRomSchema
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import (
    fs_asset_handler,
    fs_firmware_handler,
    fs_resource_handler,
    fs_rom_handler,
)
from handler.filesystem.roms_handler import FSRom, build_empty_fs_rom
from handler.metadata import (
    meta_csdb_handler,
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_libretro_handler,
    meta_moby_handler,
    meta_pouet_handler,
    meta_ra_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.csdb_handler import CsdbRom
from handler.metadata.demozoo_handler import DemozooRom
from handler.metadata.flashpoint_handler import FlashpointRom
from handler.metadata.gamelist_handler import GamelistRom
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.hltb_handler import HLTBRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.launchbox_handler.types import LaunchboxRom
from handler.metadata.libretro_handler import LibretroRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.platform_names import resolve_platform_name
from handler.metadata.pouet_handler import PouetRom
from handler.metadata.ra_handler import RAGameRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import (
    SSRom,
    add_ss_auth_to_url,
    get_preferred_media_types,
)
from handler.metadata.steam_handler import SteamRom
from handler.scan.lookups import RomLookups
from handler.scan.merge import (
    apply_artwork_priority,
    apply_metadata_priority,
    apply_sgdb_match,
    build_metadata_handlers,
    clear_rehash_misses,
    follow_demozoo_link,
    keep_base_fields,
    merge_tags,
    order_merge_sources,
    record_dump_tags,
    reset_rematched_sources,
    resolve_scene_lock,
    seed_rom_attrs,
    splice_scene_summaries,
)
from handler.scan.sources import LOGGER_MODULE_NAME, MetadataSource, ScanType
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import MemoryCardVersion, Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import METADATA_SOURCE_COLUMNS, Rom, RomFile, RomFileCategory
from models.user import User
from utils import emoji
from utils.audio_tags import persist_embedded_cover, remove_persisted_cover
from utils.concurrency import gather_all
from utils.filesystem import sanitize_filename
from utils.platform_aliases import (
    resolve_fs_folder,
    resolve_fs_slug,
    resolve_platform_slug,
)

# Sentinel folder for manually-added physical games; it never exists on disk.
PHYSICAL_FS_SUBDIR = ".physical"


def build_physical_fs_path(platform: Platform) -> str:
    """Sentinel `fs_path` for a file-less physical game on the given platform."""
    return (
        f"{fs_rom_handler.get_roms_fs_structure(platform.fs_slug)}/{PHYSICAL_FS_SUBDIR}"
    )


def build_physical_fs_name(name: str) -> str:
    """`fs_name` for a physical game: the sanitized name, with no fake extension.

    Physical games all share one folder, so the unique index on
    (platform_id, full_path_hash) rejects a second copy of the same title on a
    platform, which is not a library a user can own anyway.
    """
    return sanitize_filename(name)


def build_hashless_fs_rom(fs_name: str, fs_path: str, *, flat: bool) -> FSRom:
    """An `FSRom` for a rom with no filesystem listing to consult."""
    return build_empty_fs_rom(fs_name, fs_path, flat=flat)


def persist_soundtrack_cover(rom_file: RomFile, rom: Rom) -> None:
    """Persist a scanned soundtrack file's embedded cover and record its path on
    the track_meta row. No-op for non-soundtrack files or ones without a cover."""
    track_meta = rom_file.track_meta
    if not (rom_file.category == RomFileCategory.SOUNDTRACK and track_meta):
        return

    if not track_meta.has_embedded_cover:
        # The cover was stripped from the file since the last scan. Keep the
        # path when the unlink fails, so the next scan retries it rather than
        # stranding the file with nothing pointing at it.
        if track_meta.cover_path and remove_persisted_cover(track_meta.cover_path):
            db_rom_handler.upsert_track_meta(rom_file.id, rom.id, {"cover_path": None})
        return

    abs_audio_path = fs_rom_handler.validate_path(rom_file.full_path)
    cover_path = persist_embedded_cover(
        audio_full_path=str(abs_audio_path),
        platform_id=rom.platform_id,
        rom_id=rom.id,
        file_id=rom_file.id,
    )
    if cover_path:
        db_rom_handler.upsert_track_meta(
            rom_file.id, rom.id, {"cover_path": cover_path}
        )
    else:
        log.error(f"[audio_tags] cover persist failed for {abs_audio_path}")
        db_rom_handler.upsert_track_meta(
            rom_file.id, rom.id, {"has_embedded_cover": False}
        )


async def scan_platform(
    fs_slug: str,
    fs_platforms: list[str],
) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """
    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    cnfg = cm.get_config()

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"{hl(fs_slug)} not found in file system, trying to match via config",
            extra=LOGGER_MODULE_NAME,
        )
        platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
        if platform:
            known_fs_slug = resolve_fs_slug(platform.slug, cnfg)
            if known_fs_slug:
                # `resolve_fs_slug` answers with a lowercased config key, but
                # every path is built from the folder's own casing.
                platform_attrs["fs_slug"] = (
                    resolve_fs_folder(known_fs_slug, fs_platforms) or known_fs_slug
                )

    platform_attrs["slug"] = resolve_platform_slug(fs_slug, cnfg)

    igdb_platform = meta_igdb_handler.get_platform(platform_attrs["slug"])
    moby_platform = meta_moby_handler.get_platform(platform_attrs["slug"])
    ss_platform = meta_ss_handler.get_platform(platform_attrs["slug"])
    ra_platform = meta_ra_handler.get_platform(platform_attrs["slug"])
    launchbox_platform = meta_launchbox_handler.get_platform(platform_attrs["slug"])
    hasheous_platform = meta_hasheous_handler.get_platform(platform_attrs["slug"])
    tgdb_platform = meta_tgdb_handler.get_platform(platform_attrs["slug"])
    flashpoint_platform = meta_flashpoint_handler.get_platform(platform_attrs["slug"])
    hltb_platform = meta_hltb_handler.get_platform(platform_attrs["slug"])
    libretro_platform = meta_libretro_handler.get_platform(platform_attrs["slug"])

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update(
        {
            **libretro_platform,
            **hltb_platform,
            **flashpoint_platform,
            **tgdb_platform,
            **hasheous_platform,
            **launchbox_platform,
            **ra_platform,
            **moby_platform,
            **ss_platform,
            **igdb_platform,
            "igdb_id": igdb_platform.get("igdb_id")
            or hasheous_platform.get("igdb_id")
            or None,
            "ra_id": ra_platform.get("ra_id") or hasheous_platform.get("ra_id") or None,
            "tgdb_id": moby_platform.get("tgdb_id")
            or hasheous_platform.get("tgdb_id")
            or tgdb_platform.get("tgdb_id")
            or None,
            "name": resolve_platform_name(platform_attrs["slug"]),
            "url_logo": igdb_platform.get("url_logo")
            or tgdb_platform.get("url_logo")
            or "",
        }
    )

    platform_attrs.update(
        await meta_igdb_handler.get_platform_discovery(platform_attrs["slug"])
    )
    platform_attrs["missing_from_fs"] = False
    scanned_platform = Platform(**platform_attrs)

    if scanned_platform.is_identified:
        log.info(
            f"Folder {hl(platform_attrs['slug'])}[{hl(fs_slug, color=LIGHTYELLOW)}] identified as {hl(platform_attrs['name'], color=BLUE)} {emoji.EMOJI_VIDEO_GAME}",
            extra={"module_name": "scan"},
        )
    else:
        log.warning(
            f"Platform {hl(platform_attrs['slug'])} not identified {emoji.EMOJI_CROSS_MARK}",
            extra=LOGGER_MODULE_NAME,
        )

    return scanned_platform


async def scan_firmware(
    platform: Platform,
    file_name: str,
    firmware: Firmware | None = None,
) -> Firmware:
    firmware_path = fs_firmware_handler.get_firmware_fs_structure(platform.fs_slug)

    # Set default properties
    firmware_attrs: dict[str, Any] = {
        "id": firmware.id if firmware else None,
        "platform_id": platform.id,
    }

    file_path = f"{firmware_path}/{file_name}"
    file_size = await fs_firmware_handler.get_file_size(file_path)

    firmware_attrs.update(
        {
            "file_path": firmware_path,
            "file_name": file_name,
            "file_size_bytes": file_size,
        }
    )

    file_hashes = await fs_firmware_handler.calculate_file_hashes(
        firmware_path=firmware_path,
        file_name=file_name,
    )

    firmware_attrs.update(**file_hashes)

    return Firmware(**firmware_attrs)


# `files` is left out so a scan does not ship every file row of every rom.
_SCANNING_ROM_EXCLUDE: Final = {
    "created_at",
    "updated_at",
    "rom_user",
    "last_modified",
    "files",
    "sibling_roms",
}


async def emit_scanning_rom(
    socket_manager: socketio.AsyncRedisManager, rom: Rom, *, is_new: bool
) -> None:
    """Report a scanned rom; `is_new` lets clients count only roms the scan added."""
    payload = SimpleRomSchema.from_orm_with_factory(rom).model_dump(
        exclude=_SCANNING_ROM_EXCLUDE
    )
    payload["is_new"] = is_new
    await socket_manager.emit("scan:scanning_rom", payload)


def _log_unidentified(
    rom_attrs: dict[str, Any], inconclusive_sources: set[MetadataSource]
) -> None:
    if inconclusive_sources:
        # Reporting a plain "not identified" here writes the ROM up as a
        # coverage gap the providers confirmed, when one of them simply
        # never answered.
        silent = ", ".join(hl(source) for source in sorted(inconclusive_sources))
        log.warning(
            f"{hl(rom_attrs['fs_name'])} not identified, but {silent} gave "
            f"no answer, so this is not a confirmed miss - an UNMATCHED "
            f"scan will retry it {emoji.EMOJI_WARNING}",
            extra=LOGGER_MODULE_NAME,
        )
    else:
        log.warning(
            f"{hl(rom_attrs['fs_name'])} not identified {emoji.EMOJI_CROSS_MARK}",
            extra=LOGGER_MODULE_NAME,
        )


def _log_identified(rom_attrs: dict[str, Any], fs_rom: FSRom) -> None:
    log.info(
        f"{hl(rom_attrs['fs_name'])} identified as {hl(rom_attrs.get('name', rom_attrs['fs_name']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
        extra=LOGGER_MODULE_NAME,
    )
    if not fs_rom["flat"]:
        for file in fs_rom["files"]:
            log.info(
                f"\t · {hl(file.file_name, color=LIGHTYELLOW)}",
                extra=LOGGER_MODULE_NAME,
            )


async def scan_rom(
    scan_type: ScanType,
    platform: Platform,
    rom: Rom,
    fs_rom: FSRom,
    metadata_sources: list[str],
    newly_added: bool,
    launchbox_remote_enabled: bool = True,
    socket_manager: socketio.AsyncRedisManager | None = None,
) -> Rom:
    rom_attrs = seed_rom_attrs(scan_type, platform, rom, fs_rom, newly_added)
    is_complete_rescan = not newly_added and scan_type == ScanType.COMPLETE

    lookups = RomLookups(
        scan_type=scan_type,
        platform=platform,
        rom=rom,
        fs_rom=fs_rom,
        rom_attrs=rom_attrs,
        metadata_sources=metadata_sources,
        newly_added=newly_added,
        launchbox_remote_enabled=launchbox_remote_enabled,
    )

    # A new rom is already the reloaded row its caller inserted. An existing one
    # is written so its rescanned columns land before identification.
    scanning_rom = rom if newly_added else db_rom_handler.add_rom(Rom(**rom_attrs))
    scanning_rom.is_identifying = True

    if socket_manager:
        await emit_scanning_rom(socket_manager, scanning_rom, is_new=newly_added)

    # Run hash fetches concurrently
    (
        playmatch_hash_match,
        (hasheous_hash_match, hasheous_lookup_conclusive),
    ) = await asyncio.gather(
        lookups.fetch_playmatch_hash_match(),
        lookups.fetch_hasheous_hash_match(),
    )

    # Run metadata fetches concurrently. One provider raising must not discard the
    # others' results for this ROM, so each failure falls back to an empty match.
    provider_fetches = (
        (
            MetadataSource.IGDB,
            lookups.fetch_igdb_rom(playmatch_hash_match, hasheous_hash_match),
            IGDBRom(igdb_id=None),
        ),
        (
            MetadataSource.MOBY,
            lookups.fetch_moby_rom(playmatch_hash_match),
            MobyGamesRom(moby_id=None),
        ),
        (
            MetadataSource.SS,
            lookups.fetch_ss_rom(playmatch_hash_match),
            SSRom(ss_id=None),
        ),
        (MetadataSource.RA, lookups.fetch_ra_rom(), RAGameRom(ra_id=None)),
        (
            MetadataSource.LAUNCHBOX,
            lookups.fetch_launchbox_rom(playmatch_hash_match),
            LaunchboxRom(launchbox_id=None),
        ),
        (
            MetadataSource.HASHEOUS,
            lookups.fetch_hasheous_rom(hasheous_hash_match),
            HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None),
        ),
        (
            MetadataSource.FLASHPOINT,
            lookups.fetch_flashpoint_rom(),
            FlashpointRom(flashpoint_id=None),
        ),
        (MetadataSource.HLTB, lookups.fetch_hltb_rom(), HLTBRom(hltb_id=None)),
        (
            MetadataSource.DEMOZOO,
            lookups.fetch_demozoo_rom(),
            DemozooRom(demozoo_id=None),
        ),
        (MetadataSource.POUET, lookups.fetch_pouet_rom(), PouetRom(pouet_id=None)),
        (MetadataSource.CSDB, lookups.fetch_csdb_rom(), CsdbRom(csdb_id=None)),
        (MetadataSource.STEAM, lookups.fetch_steam_rom(), SteamRom(steam_id=None)),
        (
            MetadataSource.GAMELIST,
            lookups.fetch_gamelist_rom(),
            GamelistRom(gamelist_id=None),
        ),
        (
            MetadataSource.LIBRETRO,
            lookups.fetch_libretro_rom(),
            LibretroRom(libretro_id=None),
        ),
    )
    fetch_results = await asyncio.gather(
        *(coro for _, coro, _ in provider_fetches), return_exceptions=True
    )

    handler_roms: dict[MetadataSource, Any] = {
        source: lookups.resolve_fetch(source, result, fallback)
        for (source, _, fallback), result in zip(
            provider_fetches, fetch_results, strict=True
        )
    }

    # Filename is usually only (demozoo-N). Demozoo's Pouët and CSDb links are the
    # ids we would have used had the tag been (pouet-N) or (csdb-N).
    for source, get_rom_by_id in (
        (MetadataSource.POUET, meta_pouet_handler.get_rom_by_id),
        (MetadataSource.CSDB, meta_csdb_handler.get_rom_by_id),
    ):
        await follow_demozoo_link(source, handler_roms, get_rom_by_id, metadata_sources)
    splice_scene_summaries(handler_roms)

    metadata_handlers = build_metadata_handlers(handler_roms)

    if is_complete_rescan:
        reset_rematched_sources(
            rom_attrs, metadata_handlers, lookups.attempted_sources, metadata_sources
        )

    apply_sources, scene_locked = resolve_scene_lock(rom_attrs, metadata_handlers)

    if scan_type == ScanType.HASHES:
        clear_rehash_misses(
            rom_attrs,
            lookups.attempted_sources,
            hasheous_hash_match,
            hasheous_lookup_conclusive,
            handler_roms[MetadataSource.RA],
        )

    record_dump_tags(metadata_handlers)

    priority_ordered, hash_claims = order_merge_sources(
        apply_sources, scene_locked, metadata_handlers, rom_attrs
    )

    apply_metadata_priority(rom_attrs, metadata_handlers, priority_ordered)
    merge_tags(rom_attrs, metadata_handlers, priority_ordered, hash_claims)
    apply_artwork_priority(rom_attrs, metadata_handlers, apply_sources)

    # Don't overwrite existing base fields on update, unmatched and hashes scans
    if not newly_added and scan_type in (
        ScanType.UNMATCHED,
        ScanType.UPDATE,
        ScanType.HASHES,
    ):
        keep_base_fields(rom_attrs, rom)

    # Use PICO-8 cartridge PNG as cover art if no cover is set.
    # PICO-8 .p8.png files are valid PNG images whose visual content is the
    # cartridge label, so the ROM file itself serves as the cover art.
    if not rom_attrs.get("url_cover") and not rom_attrs.get("path_cover_s"):
        pico8_url = fs_rom_handler.get_pico8_cover_url(
            platform.slug, rom_attrs["fs_name"], rom_attrs["fs_path"]
        )
        if pico8_url:
            rom_attrs["url_cover"] = pico8_url

    # If not found in any metadata source, we return the rom with the default values
    if not any(
        rom_attrs.get(column.key) for column in METADATA_SOURCE_COLUMNS.values()
    ):
        _log_unidentified(rom_attrs, lookups.inconclusive_sources)
        return Rom(**rom_attrs)

    # SteamGridDB searches on the names the other providers just produced, so it
    # can't join the gather above, but it resolves the same way.
    (sgdb_result,) = await asyncio.gather(
        lookups.fetch_sgdb_rom(
            playmatch_hash_match,
            handler_roms,
            scene_locked=scene_locked,
        ),
        return_exceptions=True,
    )
    sgdb_handler_rom = lookups.resolve_fetch(
        MetadataSource.SGDB, sgdb_result, SGDBRom(sgdb_id=None)
    )

    # Resolving this late means missing the reset above, so clear its id here.
    if is_complete_rescan and MetadataSource.SGDB in lookups.attempted_sources:
        rom_attrs["sgdb_id"] = None

    if sgdb_handler_rom.get("sgdb_id"):
        apply_sgdb_match(rom_attrs, rom, sgdb_handler_rom, metadata_handlers)

    # Providers like libretro match without supplying a name. A new rom keeps the
    # name it was created with, which for a physical game is what the user typed.
    if not rom_attrs.get("name"):
        rom_attrs["name"] = (
            newly_added and rom.name
        ) or fs_rom_handler.get_file_name_with_no_tags(rom_attrs["fs_name"])

    _log_identified(rom_attrs, fs_rom)

    rom_attrs["missing_from_fs"] = False
    return Rom(**rom_attrs)


# The provider columns that store media, highest priority first: the order
# their files land in shared paths.
MEDIA_PROVIDERS: Final[tuple[tuple[str, str, Callable[[str], str] | None], ...]] = (
    ("ss_metadata", MetadataSource.SS, add_ss_auth_to_url),
    ("gamelist_metadata", MetadataSource.GAMELIST, None),
    ("launchbox_metadata", MetadataSource.LAUNCHBOX, None),
)


async def download_rom_resources(
    added_rom: Rom,
    previous_url_cover: str | None,
    previous_url_manual: str | None,
    previous_url_screenshots: list[str] | None,
    metadata_sources: list[str],
    previous_media: Mapping[str, dict[str, Any] | None] | None = None,
) -> None:
    """Download and persist cover, manual, screenshots and provider media for a rom.

    Shared by the scan socket flow and the manual physical-game endpoint. Only
    re-downloads when the source URL changed, then stores the resulting paths.

    Args:
        previous_media: Each provider column's metadata before this scan, keyed
            like ``ss_metadata``, so media whose source changed is fetched again.
    """
    url_screenshots = added_rom.url_screenshots or []
    # Files are named by position, so a reorder is a change too.
    screenshots_changed = url_screenshots != (previous_url_screenshots or [])

    preferred_media_types = get_preferred_media_types()
    providers = MEDIA_PROVIDERS
    provider_media: list[tuple[str, dict[str, Any], Callable[[str], str] | None]] = [
        (column, metadata, url_transform)
        for column, source, url_transform in providers
        if (metadata := getattr(added_rom, column)) and source in metadata_sources
    ]

    # Filled as each provider finishes, so a later one failing keeps the rest.
    media_updates: dict[str, dict[str, Any]] = {}

    async def store_provider_media() -> None:
        # Compared across every provider at once, before any stores, since a
        # shared path's file belongs to whichever provider records it first.
        if previous_media:
            stored_columns = {column for column, *_ in provider_media}
            await fs_resource_handler.remove_stale_media(
                [previous_media.get(column) for column, *_ in providers],
                [getattr(added_rom, column) for column, *_ in providers],
                [
                    preferred_media_types if column in stored_columns else ()
                    for column, *_ in providers
                ],
            )
        # Providers share media paths, so they take turns: a later one finds the
        # file an earlier one landed on disk and keeps it.
        for column, metadata, url_transform in provider_media:
            # Paths of media that didn't land are cleared, so the dict is written back.
            if await fs_resource_handler.store_metadata_media(
                metadata, preferred_media_types, url_transform
            ):
                media_updates[column] = metadata

    achievements = (
        added_rom.ra_metadata.get("achievements", [])
        if added_rom.ra_metadata and MetadataSource.RA in metadata_sources
        else []
    )

    # ScreenScraper media and RA badges are bounded by their own limiters. What
    # landed is saved even when another download failed, then that failure raised.
    outcomes: tuple[Any, ...] = await asyncio.gather(
        gather_all(
            fs_resource_handler.get_cover(
                entity=added_rom,
                overwrite=added_rom.url_cover != previous_url_cover,
                url_cover=add_ss_auth_to_url(added_rom.url_cover),
            ),
            fs_resource_handler.get_manual(
                rom=added_rom,
                overwrite=added_rom.url_manual != previous_url_manual,
                url_manual=add_ss_auth_to_url(added_rom.url_manual),
            ),
            fs_resource_handler.get_rom_screenshots(
                rom=added_rom,
                overwrite=screenshots_changed,
                url_screenshots=[add_ss_auth_to_url(u) for u in url_screenshots],
            ),
        ),
        store_provider_media(),
        fs_resource_handler.store_ra_badges(achievements),
        return_exceptions=True,
    )
    paths = outcomes[0]

    updates: dict[str, Any] = dict(media_updates)
    if not isinstance(paths, BaseException):
        (path_cover_s, path_cover_l), path_manual, path_screenshots = paths
        added_rom.path_cover_s = path_cover_s
        added_rom.path_cover_l = path_cover_l
        added_rom.path_screenshots = path_screenshots
        added_rom.path_manual = path_manual
        updates.update(
            path_cover_s=path_cover_s,
            path_cover_l=path_cover_l,
            path_screenshots=path_screenshots,
            path_manual=path_manual,
        )
    if updates:
        db_rom_handler.update_rom(added_rom.id, updates)
    if url_screenshots and not isinstance(paths, BaseException):
        await fs_resource_handler.remove_screenshots_past(
            added_rom, len(url_screenshots)
        )

    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            raise outcome


async def refresh_provider_media(
    rom: Rom, pending: Mapping[str, dict[str, Any] | None]
) -> dict[str, dict[str, Any]]:
    """Bring a rom's provider media in line with re-matched metadata.

    Args:
        rom: The rom, still holding each provider's stored metadata.
        pending: The metadata about to be stored, keyed like ``ss_metadata``;
            a provider left out keeps what the rom holds.

    Returns:
        The dicts whose paths were cleared because their media didn't land.
    """
    preferred_media_types = get_preferred_media_types()
    current = [
        pending[column] if column in pending else getattr(rom, column)
        for column, *_ in MEDIA_PROVIDERS
    ]
    await fs_resource_handler.remove_stale_media(
        [getattr(rom, column) for column, *_ in MEDIA_PROVIDERS],
        current,
        [preferred_media_types if metadata else () for metadata in current],
    )

    updates: dict[str, dict[str, Any]] = {}
    for (column, _source, url_transform), metadata in zip(
        MEDIA_PROVIDERS, current, strict=True
    ):
        if metadata and await fs_resource_handler.store_metadata_media(
            metadata, preferred_media_types, url_transform
        ):
            updates[column] = metadata
    return updates


class ScannedAsset(TypedDict):
    file_path: str
    file_name: str
    file_size_bytes: int
    content_hash: NotRequired[str | None]


async def _scan_asset(
    file_name: str, asset_path: str, should_hash: bool = False
) -> ScannedAsset:
    file_path = f"{asset_path}/{file_name}"
    file_size = await fs_asset_handler.get_file_size(file_path)

    result: ScannedAsset = {
        "file_path": asset_path,
        "file_name": file_name,
        "file_size_bytes": file_size,
    }

    if should_hash:
        result["content_hash"] = await fs_asset_handler.compute_content_hash(file_path)

    return result


async def scan_save(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, saves_path, should_hash=True)
    return Save(**scanned_asset)


async def scan_state(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
    content_hash: str | None = None,
) -> State:
    """`content_hash` skips the re-read, for a caller that hashed the bytes already."""
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(
        file_name, states_path, should_hash=content_hash is None
    )
    if content_hash is not None:
        scanned_asset["content_hash"] = content_hash
    return State(**scanned_asset)


async def scan_memory_card_version(
    file_name: str,
    user: User,
    emulator: str,
    card_id: int,
    content_hash: str | None = None,
) -> MemoryCardVersion:
    """Scan a card archive that is already on disk.

    `content_hash` skips the re-read: a caller that hashed the same bytes in
    memory has the answer already, and a card archive runs to hundreds of
    megabytes.
    """
    cards_path = fs_asset_handler.build_memory_cards_file_path(
        user=user, emulator=emulator, card_id=card_id
    )
    scanned_asset = await _scan_asset(
        file_name, cards_path, should_hash=content_hash is None
    )
    if content_hash is not None:
        scanned_asset["content_hash"] = content_hash
    return MemoryCardVersion(**scanned_asset, memory_card_id=card_id)


async def scan_screenshot(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, screenshots_path)
    return Screenshot(**scanned_asset)
