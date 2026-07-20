from datetime import datetime, timezone

from config.config_manager import config_manager as cm
from endpoints.responses.platform import PlatformSchema
from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.platform import Platform


def _build_unmatched_platform(slug: str, fs_slug: str, now: datetime) -> PlatformSchema:
    """Build a PlatformSchema for a platform that has no database row yet.

    Metadata is resolved from the local provider catalogs only (no network
    calls). The entry carries id -1 and rom_count 0, matching the shape used
    for unmatched supported platforms.
    """
    igdb_platform = meta_igdb_handler.get_platform(slug)
    moby_platform = meta_moby_handler.get_platform(slug)
    ss_platform = meta_ss_handler.get_platform(slug)
    ra_platform = meta_ra_handler.get_platform(slug)
    launchbox_platform = meta_launchbox_handler.get_platform(slug)
    hasheous_platform = meta_hasheous_handler.get_platform(slug)
    tgdb_platform = meta_tgdb_handler.get_platform(slug)
    flashpoint_platform = meta_flashpoint_handler.get_platform(slug)
    hltb_platform = meta_hltb_handler.get_platform(slug)

    platform_attrs = {
        "id": -1,
        "name": slug.replace("-", " ").title(),
        "fs_slug": fs_slug,
        "slug": slug,
        "roms": [],
        "rom_count": 0,
        "created_at": now,
        "updated_at": now,
        "fs_size_bytes": 0,
        "missing_from_fs": False,
    }

    platform_attrs.update(
        {
            **hltb_platform,
            **flashpoint_platform,
            **hasheous_platform,
            **tgdb_platform,
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
            "name": igdb_platform.get("name")
            or ss_platform.get("name")
            or moby_platform.get("name")
            or ra_platform.get("name")
            or launchbox_platform.get("name")
            or hasheous_platform.get("name")
            or tgdb_platform.get("name")
            or flashpoint_platform.get("name")
            or hltb_platform.get("name")
            or slug.replace("-", " ").title(),
            "url_logo": igdb_platform.get("url_logo")
            or tgdb_platform.get("url_logo")
            or "",
        }
    )

    return PlatformSchema.model_validate(Platform(**platform_attrs))


def get_supported_platforms() -> list[PlatformSchema]:
    """Get all supported platforms with metadata from various sources.

    Returns:
        List of platform dictionaries with metadata from IGDB, MobyGames,
        ScreenScraper, RetroAchievements, Launchbox, Hasheous, TGDB,
        Flashpoint, and HowLongToBeat.
    """
    db_platforms = db_platform_handler.get_platforms()

    # Multiple folders can resolve to the same slug (a folder alias or a
    # platform variant bound to a parent platform). When that happens, prefer
    # the canonical platform (the one whose fs_slug matches its slug) so a
    # variant folder doesn't shadow the parent and rename it in the picker.
    db_platforms_map: dict[str, Platform] = {}
    for p in db_platforms:
        existing = db_platforms_map.get(p.slug)
        if existing is None or p.fs_slug == p.slug:
            db_platforms_map[p.slug] = p

    now = datetime.now(timezone.utc)
    supported_platforms = []

    for upslug in UPS:
        slug = upslug.value

        db_platform = db_platforms_map.get(slug, None)
        if db_platform:
            supported_platforms.append(PlatformSchema.model_validate(db_platform))
            continue

        supported_platforms.append(_build_unmatched_platform(slug, slug, now))

    return supported_platforms


async def get_filesystem_platforms() -> list[PlatformSchema]:
    """Get platform folders that exist on disk but have no database row yet.

    A folder created for a platform (optionally bound in Library Management)
    has no database row until its first scan imports a ROM, so it is invisible
    to the scan platform picker. Surfacing these folders lets a first scan
    target a brand-new platform. Slugs are resolved through the platform
    binding/version config; metadata is resolved locally (no network calls).
    """
    cnfg = cm.get_config()
    fs_slugs = await fs_platform_handler.get_platforms()
    existing_fs_slugs = {p.fs_slug for p in db_platform_handler.get_platforms()}

    now = datetime.now(timezone.utc)
    filesystem_platforms = []

    for fs_slug in fs_slugs:
        if fs_slug in existing_fs_slugs:
            continue

        slug = (
            cnfg.PLATFORMS_BINDING.get(fs_slug)
            or cnfg.PLATFORMS_VERSIONS.get(fs_slug)
            or fs_slug
        )
        filesystem_platforms.append(_build_unmatched_platform(slug, fs_slug, now))

    return filesystem_platforms
