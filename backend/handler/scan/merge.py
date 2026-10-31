"""Merging the metadata sources' answers into a rom's columns."""

from collections.abc import Awaitable, Callable
from typing import Any

from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata.demozoo_handler import (
    _append_unique,
    splice_csdb_url,
    splice_pouet_vote,
)
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.scan.sources import (
    DUMP_TAG_KEYS,
    HASH_MATCHED_TAG_SOURCES,
    LOGGER_MODULE_NAME,
    PROVIDER_ALL_TAG_FIELDS,
    PROVIDER_MERGED_TAG_FIELDS,
    PROVIDER_TAG_FIELDS,
    RESCAN_RULES,
    SCENE_METADATA_SOURCES,
    MetadataSource,
    ScanType,
    get_priority_ordered_metadata_sources,
)
from logger.formatter import highlight as hl
from logger.logger import log
from models.platform import Platform
from models.rom import PROVIDER_METADATA_COLUMNS, Rom, RomIdentity


def hash_source_tags(
    fields: dict[str, Any], rom_attrs: dict[str, Any]
) -> tuple[dict[str, list[str]], bool]:
    """The tags a hash-matched source vouches for, and whether it said so this scan.

    Args:
        fields: The source's entry in the scan's handler table, its blob already
            holding this scan's dump tags.
        rom_attrs: The ROM's attributes, still holding its stored ids and blobs.

    Returns:
        Each tag field's values, empty when the source doesn't cover the ROM, and
        whether they are this scan's answer rather than the stored one.
    """
    handler = fields["handler"]
    answered = bool(handler.get(fields["id_field"]))
    if answered:
        blob = handler.get(fields["metadata_field"]) or {}
    elif rom_attrs.get(fields["id_field"]):
        blob = rom_attrs.get(fields["metadata_field"]) or {}
    else:
        blob = {}
    # A hand edit of the raw metadata can store any JSON; only lists of strings count.
    if not isinstance(blob, dict):
        blob = {}
    claims = {}
    for field in PROVIDER_ALL_TAG_FIELDS:
        value = blob.get(DUMP_TAG_KEYS[field])
        claims[field] = (
            [tag for tag in value if isinstance(tag, str)]
            if isinstance(value, list)
            else []
        )
    return claims, answered


def scene_apply_sources(
    available_sources: list[MetadataSource],
    *,
    scene_locked: bool = False,
) -> list[MetadataSource]:
    """Sources allowed to write identity and artwork for this ROM.

    Scene-matched ROMs stay on Demozoo/Pouët/CSDb. Everything else is unchanged.
    A ROM already carrying a scene id stays locked even when this scan's scene
    lookup came back empty, so an unreachable provider can't hand a known
    production back to the catalogs.
    """
    scene = [source for source in available_sources if source in SCENE_METADATA_SOURCES]
    if scene:
        return scene
    return [] if scene_locked else list(available_sources)


def fs_rom_file_attrs(fs_rom: FSRom) -> dict[str, Any]:
    """The hash, size and title id columns a listed `fs_rom` sets on its rom."""
    if not fs_rom["files"]:
        return {}

    attrs: dict[str, Any] = {
        "crc_hash": fs_rom["crc_hash"],
        "md5_hash": fs_rom["md5_hash"],
        "sha1_hash": fs_rom["sha1_hash"],
        "ra_hash": fs_rom["ra_hash"],
        "fs_size_bytes": sum(file.file_size_bytes for file in fs_rom["files"]),
    }
    # Only when extraction produced an id, so a hash-only or extraction-disabled
    # rescan can't wipe the stored one.
    identity = fs_rom.get("identity")
    if identity and identity.title_id:
        attrs.update(identity.as_rom_attrs())
    return attrs


def seed_rom_attrs(
    scan_type: ScanType,
    platform: Platform,
    rom: Rom,
    fs_rom: FSRom,
    newly_added: bool,
) -> dict[str, Any]:
    """The columns a scan of `rom` starts from, before any source answers."""
    rom_attrs = {
        "id": rom.id,
        "platform_id": platform.id,
        "fs_name": fs_rom["fs_name"],
        "fs_path": rom.fs_path,
        "regions": rom.regions,
        "revision": rom.revision,
        "version": rom.version,
        "languages": rom.languages,
        "tags": rom.tags,
        "crc_hash": rom.crc_hash,
        "md5_hash": rom.md5_hash,
        "sha1_hash": rom.sha1_hash,
        "ra_hash": rom.ra_hash,
        **RomIdentity.from_rom(rom).as_rom_attrs(),
        "fs_size_bytes": rom.fs_size_bytes,
        "is_physical": rom.is_physical,
        "upc": rom.upc,
    }

    file_attrs = fs_rom_file_attrs(fs_rom)
    rom_attrs.update(file_attrs)
    if file_attrs.get("title_id"):
        # Metadata matching reads the id off the instance, so a rescan searches
        # by what was just extracted rather than the stored value.
        rom.title_id = file_attrs["title_id"]

    # Every rescan keeps the stored artwork paths, so a file no provider replaces
    # survives one that is down.
    if not newly_added:
        rom_attrs.update(
            {
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "path_manual": rom.path_manual,
            }
        )

    # Update properties from existing rom if not a complete rescan
    if not newly_added and scan_type != ScanType.COMPLETE:
        rom_attrs.update(
            {
                "name": rom.name,
                "name_sort_key": rom.name_sort_key,
                "slug": rom.slug,
                "summary": rom.summary,
                "url_cover": rom.url_cover,
                "url_screenshots": rom.url_screenshots,
                "url_manual": rom.url_manual,
                "locked_fields": rom.locked_fields,
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "ss_id": rom.ss_id,
                "sgdb_id": rom.sgdb_id,
                "ra_id": rom.ra_id,
                "launchbox_id": rom.launchbox_id,
                "hasheous_id": rom.hasheous_id,
                "tgdb_id": rom.tgdb_id,
                "gamelist_id": rom.gamelist_id,
                "flashpoint_id": rom.flashpoint_id,
                "hltb_id": rom.hltb_id,
                "demozoo_id": rom.demozoo_id,
                "pouet_id": rom.pouet_id,
                "csdb_id": rom.csdb_id,
                "steam_id": rom.steam_id,
                "libretro_id": rom.libretro_id,
                **{c: getattr(rom, c) for c in PROVIDER_METADATA_COLUMNS},
            }
        )

    return rom_attrs


async def follow_demozoo_link(
    source: MetadataSource,
    handler_roms: dict[MetadataSource, Any],
    get_rom_by_id: Callable[[int], Awaitable[Any]],
    metadata_sources: list[str],
) -> None:
    """Match `source` by the id Demozoo links to, when the scan found none itself."""
    id_field = RESCAN_RULES[source].id_field
    if source not in metadata_sources or handler_roms[source].get(id_field):
        return
    demozoo_metadata = handler_roms[MetadataSource.DEMOZOO].get("demozoo_metadata")
    linked = (demozoo_metadata or {}).get(id_field)
    if not linked:
        return
    try:
        followed = await get_rom_by_id(int(linked))
    except Exception as exc:
        log.error(
            f"Error following Demozoo {source} id {hl(str(linked))}: {exc}",
            extra=LOGGER_MODULE_NAME,
        )
        return
    if followed.get(id_field):
        handler_roms[source] = followed


def splice_scene_summaries(handler_roms: dict[MetadataSource, Any]) -> None:
    """Keep Demozoo's richer summary, adding Pouët's votes and links and the CSDb page."""
    demozoo_rom = handler_roms[MetadataSource.DEMOZOO]
    pouet_rom = handler_roms[MetadataSource.POUET]
    csdb_rom = handler_roms[MetadataSource.CSDB]

    # Pouët is later in metadata priority, so its short summary would
    # replace Demozoo's party / credits / YouTube.
    if demozoo_rom.get("demozoo_id") and pouet_rom.get("pouet_id"):
        dz_meta = demozoo_rom.get("demozoo_metadata") or {}
        pq_meta = pouet_rom.get("pouet_metadata") or {}
        merged = splice_pouet_vote(
            str(demozoo_rom.get("summary") or ""),
            pq_meta.get("vote_avg"),
            pq_meta.get("pouet_rank"),
            pq_meta.get("pouet_cdc"),
        )
        if merged:
            demozoo_rom["summary"] = merged
            pouet_rom["summary"] = merged
        urls: list[str] = []
        for url in (dz_meta.get("download_urls") or []) + (
            pq_meta.get("download_urls") or []
        ):
            _append_unique(urls, url)
        if urls:
            dz_meta["download_urls"] = urls
            pq_meta["download_urls"] = urls
        if not dz_meta.get("youtube_video_id") and pq_meta.get("youtube_video_id"):
            dz_meta["youtube_video_id"] = pq_meta["youtube_video_id"]
        demozoo_rom["demozoo_metadata"] = dz_meta
        pouet_rom["pouet_metadata"] = pq_meta

    csdb_url = (csdb_rom.get("csdb_metadata") or {}).get("csdb_url") or (
        (demozoo_rom.get("demozoo_metadata") or {}).get("csdb_url")
    )
    if csdb_url:
        for blob in (demozoo_rom, pouet_rom, csdb_rom):
            if blob.get("summary") or blob.get("csdb_id") or blob.get("demozoo_id"):
                merged_csdb = splice_csdb_url(str(blob.get("summary") or ""), csdb_url)
                if merged_csdb:
                    blob["summary"] = merged_csdb


def build_metadata_handlers(
    handler_roms: dict[MetadataSource, Any],
) -> dict[MetadataSource, dict[str, Any]]:
    """Each source's answer beside the columns it fills."""
    metadata_handlers: dict[MetadataSource, dict[str, Any]] = {
        source: {
            "handler": handler_rom,
            "id_field": RESCAN_RULES[source].id_field,
            "metadata_field": RESCAN_RULES[source].metadata_field,
        }
        for source, handler_rom in handler_roms.items()
    }
    # SteamGridDB answers after the merge, so its entry starts out empty.
    metadata_handlers.setdefault(
        MetadataSource.SGDB,
        {
            "handler": {},
            "id_field": RESCAN_RULES[MetadataSource.SGDB].id_field,
            "metadata_field": RESCAN_RULES[MetadataSource.SGDB].metadata_field,
        },
    )
    # No scan consults TheGamesDB, so it has no rule, but a rescan still resets it.
    metadata_handlers[MetadataSource.TGDB] = {
        "handler": {},
        "id_field": "tgdb_id",
        "metadata_field": None,
    }
    return metadata_handlers


def reset_rematched_sources(
    rom_attrs: dict[str, Any],
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
    attempted_sources: set[MetadataSource],
    metadata_sources: list[str],
) -> None:
    """Clear what a complete rescan rematches, so a miss undoes the old match."""
    # The consulted sources and the deselected ones are the ones it can rematch.
    for source, fields in metadata_handlers.items():
        if source in attempted_sources or source not in metadata_sources:
            rom_attrs[fields["id_field"]] = None
            if fields["metadata_field"]:
                rom_attrs[fields["metadata_field"]] = {}

    # Clear the sources and locks so whatever answers now can replace a file.
    rom_attrs.update(
        {
            "url_cover": "",
            "url_screenshots": [],
            "url_manual": "",
            "locked_fields": [],
        }
    )


def resolve_scene_lock(
    rom_attrs: dict[str, Any], metadata_handlers: dict[MetadataSource, dict[str, Any]]
) -> tuple[list[MetadataSource], bool]:
    """The sources allowed to write the rom, and whether it is a scene production."""
    available_sources = [
        name
        for name, fields in metadata_handlers.items()
        if fields["handler"].get(fields["id_field"])
    ]
    # A persisted id locks the ROM too, so an unreachable provider can't hand an
    # identified production back to the catalogs. Deselecting the source on a
    # complete rescan clears the id, which is the way out.
    scene_locked = any(
        source in SCENE_METADATA_SOURCES for source in available_sources
    ) or any(
        rom_attrs.get(metadata_handlers[source]["id_field"])
        for source in SCENE_METADATA_SOURCES
    )
    if scene_locked:
        log.info(
            f"{hl(rom_attrs['fs_name'])} is a Demozoo/Pouët/CSDb production, "
            "using scene artwork and title, not similar game catalogs",
            extra=LOGGER_MODULE_NAME,
        )
    return (
        scene_apply_sources(available_sources, scene_locked=scene_locked),
        scene_locked,
    )


def clear_rehash_misses(
    rom_attrs: dict[str, Any],
    attempted_sources: set[MetadataSource],
    hasheous_hash_match: HasheousRom,
    hasheous_lookup_conclusive: bool,
    ra_handler_rom: Any,
) -> None:
    """Drop the hash matches a rehash no longer earns."""
    # Otherwise the ROM keeps showing verification flags earned by hashes it no
    # longer has. Only a conclusive lookup clears them, so an unreachable
    # Hasheous can't silently de-verify a library.
    if hasheous_lookup_conclusive and not hasheous_hash_match.get("hasheous_id"):
        rom_attrs["hasheous_id"] = None
        rom_attrs["hasheous_metadata"] = {}

    # Same for the RA hash match, once an RA lookup that ran found nothing.
    ra_metadata = rom_attrs.get("ra_metadata") or {}
    if (
        MetadataSource.RA in attempted_sources
        and not ra_handler_rom.get("ra_id")
        and ra_metadata.get("hash_match")
    ):
        rom_attrs["ra_metadata"] = {**ra_metadata, "hash_match": False}


def record_dump_tags(metadata_handlers: dict[MetadataSource, dict[str, Any]]) -> None:
    """Copy each hash source's dump tags into its own blob."""
    # A skipped source's tags can't be told apart on the row.
    for source_name in HASH_MATCHED_TAG_SOURCES:
        fields = metadata_handlers[source_name]
        handler = fields["handler"]
        if handler.get(fields["id_field"]):
            dump_tags = {
                DUMP_TAG_KEYS[field]: list(handler.get(field) or [])
                for field in PROVIDER_ALL_TAG_FIELDS
            }
            blob = {**(handler.get(fields["metadata_field"]) or {}), **dump_tags}
            fields["handler"] = {**handler, fields["metadata_field"]: blob}


def order_merge_sources(
    apply_sources: list[MetadataSource],
    scene_locked: bool,
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
    rom_attrs: dict[str, Any],
) -> tuple[list[MetadataSource], list[tuple[dict[str, list[str]], bool]]]:
    """The sources to merge in priority order, and the hash-matched sources' tag claims."""
    # One ordering pass for both lists, since each one rereads config.yml.
    hash_sources = [] if scene_locked else list(HASH_MATCHED_TAG_SOURCES)
    ordered = get_priority_ordered_metadata_sources(
        list(dict.fromkeys([*apply_sources, *hash_sources])), "metadata"
    )
    priority_ordered = [source for source in ordered if source in apply_sources]
    hash_claims = [
        hash_source_tags(metadata_handlers[source], rom_attrs)
        for source in ordered
        if source in hash_sources
    ]
    return priority_ordered, hash_claims


def apply_metadata_priority(
    rom_attrs: dict[str, Any],
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
    priority_ordered: list[MetadataSource],
) -> None:
    """Write each source's non-empty fields, the highest priority last."""
    for source_name in reversed(priority_ordered):
        for key, field_value in metadata_handlers[source_name]["handler"].items():
            if (
                key in PROVIDER_ALL_TAG_FIELDS
                and source_name in HASH_MATCHED_TAG_SOURCES
            ):
                continue
            if field_value:
                rom_attrs[key] = field_value


def merge_tags(
    rom_attrs: dict[str, Any],
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
    priority_ordered: list[MetadataSource],
    hash_claims: list[tuple[dict[str, list[str]], bool]],
) -> None:
    """Settle the tag fields from the filename, the catalogs and the hash sources."""
    # Re-read rather than taken off the row, which cannot say whether its value
    # is a tag the user wrote or what a provider left there on an earlier scan.
    filename_tags = fs_rom_handler.parse_tags(rom_attrs["fs_name"])
    local_tags = {
        "regions": filename_tags.regions,
        "languages": filename_tags.languages,
        "tags": filename_tags.other_tags,
    }
    catalog_handlers = [
        metadata_handlers[source_name]["handler"]
        for source_name in priority_ordered
        if source_name not in HASH_MATCHED_TAG_SOURCES
    ]

    for field in PROVIDER_TAG_FIELDS:
        if local_tags[field] or any(handler.get(field) for handler in catalog_handlers):
            continue
        for claims, answered in hash_claims:
            # What a source said on an earlier scan fills only an empty slot: the
            # row's value may come from a source this scan didn't ask either.
            if claims[field] and (answered or not rom_attrs.get(field)):
                rom_attrs[field] = claims[field]
                break

    for field in PROVIDER_MERGED_TAG_FIELDS:
        # The base is what a local source says now, never the stored list: a
        # dump that stops being a translation has to lose the tag again.
        claimed = next(
            (handler[field] for handler in catalog_handlers if handler.get(field)),
            local_tags[field],
        )
        merged_tags = list(claimed)
        for claims, _ in hash_claims:
            for tag in claims[field]:
                if tag not in merged_tags:
                    merged_tags.append(tag)
        rom_attrs[field] = merged_tags


def apply_artwork_priority(
    rom_attrs: dict[str, Any],
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
    apply_sources: list[MetadataSource],
) -> None:
    """Write the artwork urls, each field under its own priority override."""
    for field in ["url_cover", "url_screenshots", "url_manual"]:
        priority_ordered_artwork = get_priority_ordered_metadata_sources(
            apply_sources, field
        )
        for source_name in reversed(priority_ordered_artwork):
            field_value = metadata_handlers[source_name]["handler"].get(field)
            if field_value:
                rom_attrs[field] = field_value


def keep_base_fields(rom_attrs: dict[str, Any], rom: Rom) -> None:
    """Hold the stored name, summary and locked artwork against a refresh."""
    # A ROM's name defaults to a filename-derived placeholder when first
    # created. Treat that placeholder as "no name" so a freshly matched provider
    # name replaces it (while preserving user-edited names).
    fs_name_no_tags = fs_rom_handler.get_file_name_with_no_tags(rom_attrs["fs_name"])
    # Both the existing name and the seeded rom_attrs name can hold the
    # placeholder. Discard either when it's a placeholder so the parsed
    # filename fallback can win.
    # The stored no-tags name is the placeholder the ROM's name was seeded from.
    placeholders = (None, "", rom.fs_name, fs_name_no_tags, rom.fs_name_no_tags)
    existing_name = None if rom.name in placeholders else rom.name
    matched_name = rom_attrs.get("name")
    matched_name = None if matched_name in placeholders else matched_name
    rom_attrs.update(
        {
            "name": existing_name or matched_name or fs_name_no_tags or None,
            "summary": rom.summary or rom_attrs.get("summary") or None,
            # Only a locked slot resists the freshly resolved url. A stored
            # manual is pinned regardless, since one with no url was uploaded.
            "url_cover": (
                ""
                if rom.is_field_locked("url_cover")
                else rom_attrs.get("url_cover") or None
            ),
            "url_manual": (
                rom.url_manual
                if rom.url_manual
                or rom.path_manual
                or rom.is_field_locked("url_manual")
                else rom_attrs.get("url_manual") or None
            ),
            "url_screenshots": rom_attrs.get("url_screenshots") or [],
        }
    )


def apply_sgdb_match(
    rom_attrs: dict[str, Any],
    rom: Rom,
    sgdb_rom: SGDBRom,
    metadata_handlers: dict[MetadataSource, dict[str, Any]],
) -> None:
    """Record the SteamGridDB id, and its cover when it outranks the rest."""
    rom_attrs["sgdb_id"] = sgdb_rom["sgdb_id"]

    # Never over a locked cover, and only when SGDB outranks every other source
    # that already produced one under the cover priority.
    sgdb_cover = sgdb_rom.get("url_cover")
    if not sgdb_cover or rom.is_field_locked("url_cover"):
        return
    cover_sources = [
        name
        for name, fields in metadata_handlers.items()
        if fields["handler"].get("url_cover")
    ]
    ranked = get_priority_ordered_metadata_sources(
        cover_sources + [MetadataSource.SGDB], "url_cover"
    )
    if ranked[0] == MetadataSource.SGDB:
        rom_attrs["url_cover"] = sgdb_cover
