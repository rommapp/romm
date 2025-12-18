from datetime import datetime, timezone

from endpoints.responses.platform import PlatformSchema
from handler.database import db_platform_handler
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
from models.platform import DEFAULT_COVER_ASPECT_RATIO, Platform


def get_supported_platforms() -> list[PlatformSchema]:
    """Get all supported platforms with metadata from various sources.

    Returns:
        List of platform dictionaries with metadata from IGDB, MobyGames,
        ScreenScraper, RetroAchievements, Launchbox, Hasheous, TGDB,
        Flashpoint, and HowLongToBeat.
    """
    db_platforms = db_platform_handler.get_platforms()
    db_platforms_map = {p.slug: p for p in db_platforms}

    now = datetime.now(timezone.utc)
    supported_platforms = []

    for upslug in UPS:
        slug = upslug.value

        db_platform = db_platforms_map.get(slug, None)
        if db_platform:
            supported_platforms.append(
                PlatformSchema.model_validate(db_platform).model_dump()
            )
            continue

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
            "fs_slug": slug,
            "slug": slug,
            "roms": [],
            "rom_count": 0,
            "created_at": now,
            "updated_at": now,
            "fs_size_bytes": 0,
            "missing_from_fs": False,
            "aspect_ratio": DEFAULT_COVER_ASPECT_RATIO,
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
                "ra_id": ra_platform.get("ra_id")
                or hasheous_platform.get("ra_id")
                or None,
                "tgdb_id": moby_platform.get("tgdb_id")
                or hasheous_platform.get("tgdb_id")
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

        platform = Platform(**platform_attrs)
        supported_platforms.append(PlatformSchema.model_validate(platform))

    return supported_platforms
