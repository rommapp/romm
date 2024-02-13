from typing import Any

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

SWAPPED_PLATFORM_BINDINGS = dict((v, k) for k, v in cm.config.PLATFORMS_BINDING.items())


def _get_main_platform_igdb_id(platform: Platform):
    if platform.fs_slug in cm.config.PLATFORMS_VERSIONS.keys():
        main_platform_slug = cm.config.PLATFORMS_VERSIONS[platform.fs_slug]
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

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"  {fs_slug} not found in file system, trying to match via config..."
        )
        if fs_slug in SWAPPED_PLATFORM_BINDINGS.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = SWAPPED_PLATFORM_BINDINGS[platform.slug]

    try:
        if fs_slug in cm.config.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = cm.config.PLATFORMS_BINDING[fs_slug]
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
) -> Rom:
    roms_path = fs_rom_handler.get_fs_structure(platform.fs_slug)

    log.info(f"\t · {rom_attrs['file_name']}")

    if rom_attrs.get("multi", False):
        for file in rom_attrs["files"]:
            log.info(f"\t\t · {file}")

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
            "igdb_id": None,
            "moby_id": None,
            "slug": "",
            "name": rom_attrs["file_name"],
            "summary": "",
            "url_cover": "",
            "url_screenshots": [],
            "platform_id": platform.id,
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

    main_platform_igdb_id = _get_main_platform_igdb_id(platform)
    igdb_handler_rom = await igdb_handler.get_rom(
        rom_attrs["file_name"], main_platform_igdb_id
    )
    moby_handler_rom = await moby_handler.get_rom(
        rom_attrs["file_name"], platform.moby_id
    )

    # Return early if not found in IGDB or MobyGames
    if not igdb_handler_rom["igdb_id"] and not moby_handler_rom["moby_id"]:
        log.warning(
            emoji.emojize(
                f"\t   {rom_attrs['file_name']} not found :cross_mark:"
            )
        )
        return Rom(**rom_attrs)

    rom_attrs.update({**moby_handler_rom, **igdb_handler_rom}) # Reversed to prioritize IGDB
    log.info(emoji.emojize(f"\t   Identified as {rom_attrs['name']} :alien_monster:"))

    # Update properties from IGDB
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
