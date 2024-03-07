from typing import Any, Literal

import emoji
from config.config_manager import config_manager as cm
from handler import (
    db_platform_handler,
    fs_asset_handler,
    fs_resource_handler,
    fs_rom_handler,
    igdb_handler,
    moby_handler,
)
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom
from models.user import User

ScanType = Literal["new_platforms", "quick", "unidentified", "partial", "complete"]


def _get_main_platform_igdb_id(platform: Platform):
    cnfg = cm.get_config()

    if platform.fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
        main_platform_slug = cnfg.PLATFORMS_VERSIONS[platform.fs_slug]
        main_platform = db_platform_handler.get_platform_by_fs_slug(main_platform_slug)
        if main_platform:
            main_platform_igdb_id = main_platform.igdb_id
        else:
            main_platform_igdb_id = igdb_handler.get_platform(main_platform_slug)[
                "igdb_id"
            ]
            if not main_platform_igdb_id:
                main_platform_igdb_id = platform.igdb_id
    else:
        main_platform_igdb_id = platform.igdb_id
    return main_platform_igdb_id


def scan_platform(fs_slug: str, fs_platforms: list[str]) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """

    log.info(f"· {fs_slug}")

    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    cnfg = cm.get_config()
    swapped_platform_bindings = dict((v, k) for k, v in cnfg.PLATFORMS_BINDING.items())

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"  {fs_slug} not found in file system, trying to match via config..."
        )
        if fs_slug in swapped_platform_bindings.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_bindings[platform.slug]

    try:
        if fs_slug in cnfg.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_BINDING[fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    igdb_platform = igdb_handler.get_platform(platform_attrs["slug"])
    moby_platform = moby_handler.get_platform(platform_attrs["slug"])

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update({**moby_platform, **igdb_platform})  # Reverse order

    if platform_attrs["igdb_id"] or platform_attrs["moby_id"]:
        log.info(
            emoji.emojize(f"  Identified as {platform_attrs['name']} :video_game:")
        )
    else:
        log.warning(emoji.emojize(f" {platform_attrs['slug']} not found :cross_mark:"))

    return Platform(**platform_attrs)


async def scan_rom(
    platform: Platform,
    rom_attrs: dict,
    rom: Rom | None = None,
    scan_type: ScanType = "quick",
) -> Rom:
    roms_path = fs_rom_handler.get_fs_structure(platform.fs_slug)

    log.info(f"\t · {rom_attrs['file_name']}")

    if rom_attrs.get("multi", False):
        for file in rom_attrs["files"]:
            log.info(f"\t\t · {file}")

    # Set default properties
    rom_attrs.update(
        {
            "id": rom.id if rom else None,
            "platform_id": platform.id,
            "name": rom_attrs["file_name"],
        }
    )

    # Update properties from existing rom if not a complete rescan
    if rom and scan_type != "complete":
        rom_attrs.update(
            {
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "sgdb_id": rom.sgdb_id,
                "name": rom.name,
                "slug": rom.slug,
                "summary": rom.summary,
                "igdb_metadata": rom.igdb_metadata,
                "moby_metadata": rom.moby_metadata,
                "url_cover": rom.url_cover,
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "url_screenshots": rom.url_screenshots,
            }
        )

    # Update properties that don't require metadata
    file_size = fs_rom_handler.get_rom_file_size(
        multi=rom_attrs["multi"],
        file_name=rom_attrs["file_name"],
        multi_files=rom_attrs["files"],
        roms_path=roms_path,
    )
    regs, rev, langs, other_tags = fs_rom_handler.parse_tags(rom_attrs["file_name"])
    rom_attrs.update(
        {
            "file_path": roms_path,
            "file_name": rom_attrs["file_name"],
            "file_name_no_tags": fs_rom_handler.get_file_name_with_no_tags(
                rom_attrs["file_name"]
            ),
            "file_name_no_ext": fs_rom_handler.get_file_name_with_no_extension(
                rom_attrs["file_name"]
            ),
            "file_extension": fs_rom_handler.parse_file_extension(
                rom_attrs["file_name"]
            ),
            "file_size_bytes": file_size,
            "multi": rom_attrs["multi"],
            "regions": regs,
            "revision": rev,
            "languages": langs,
            "tags": other_tags,
        }
    )

    igdb_handler_rom = {}
    moby_handler_rom = {}

    if (
        not rom
        or scan_type == "complete"
        or (scan_type == "partial" and not rom.igdb_id)
        or (scan_type == "unidentified" and not rom.igdb_id)
    ):
        main_platform_igdb_id = _get_main_platform_igdb_id(platform)
        igdb_handler_rom = await igdb_handler.get_rom(
            rom_attrs["file_name"], main_platform_igdb_id
        )

    if (
        not rom
        or scan_type == "complete"
        or (scan_type == "partial" and not rom.moby_id)
        or (scan_type == "unidentified" and not rom.moby_id)
    ):
        moby_handler_rom = await moby_handler.get_rom(
            rom_attrs["file_name"], platform.moby_id
        )

    # Return early if not found in IGDB or MobyGames
    if not igdb_handler_rom.get("igdb_id") and not moby_handler_rom.get("moby_id"):
        log.warning(
            emoji.emojize(f"\t   {rom_attrs['file_name']} not found :cross_mark:")
        )
        return Rom(**rom_attrs)

    # Reversed to prioritize IGDB
    rom_attrs.update({**moby_handler_rom, **igdb_handler_rom})
    log.info(emoji.emojize(f"\t   Identified as {rom_attrs['name']} :alien_monster:"))

    # Update properties from IGDB
    if (
        not rom
        or scan_type == "complete"
        or (scan_type == "partial" and rom and (not rom.igdb_id or not rom.moby_id))
        or (scan_type == "unidentified" and rom and not rom.igdb_id and not rom.moby_id)
    ):
        rom_attrs.update(
            fs_resource_handler.get_rom_cover(
                overwrite=False,
                platform_fs_slug=platform.slug,
                rom_name=rom_attrs["name"],
                url_cover=rom_attrs["url_cover"],
            )
        )
        rom_attrs.update(
            fs_resource_handler.get_rom_screenshots(
                platform_fs_slug=platform.slug,
                rom_name=rom_attrs["name"],
                url_screenshots=rom_attrs["url_screenshots"],
            )
        )

    return Rom(**rom_attrs)


def _scan_asset(file_name: str, path: str):
    log.info(f"\t\t · {file_name}")

    file_size = fs_asset_handler.get_asset_size(file_name=file_name, asset_path=path)

    return {
        "file_path": path,
        "file_name": file_name,
        "file_name_no_tags": fs_asset_handler.get_file_name_with_no_tags(file_name),
        "file_name_no_ext": fs_asset_handler.get_file_name_with_no_extension(file_name),
        "file_extension": fs_asset_handler.parse_file_extension(file_name),
        "file_size_bytes": file_size,
    }


def scan_save(
    file_name: str, user: User, platform_fs_slug: str, emulator: str = None
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, emulator=emulator
    )
    return Save(**_scan_asset(file_name, saves_path))


def scan_state(
    file_name: str, user: User, platform_fs_slug: str, emulator: str = None
) -> State:
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, emulator=emulator
    )
    return State(**_scan_asset(file_name, states_path))


def scan_screenshot(
    file_name: str, user: User, platform_fs_slug: str = None
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug
    )
    return Screenshot(**_scan_asset(file_name, screenshots_path))
