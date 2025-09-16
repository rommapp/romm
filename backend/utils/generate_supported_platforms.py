# uv run python -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
)
from handler.metadata.base_handler import UniversalPlatformSlug


class SupportedPlatform(TypedDict):
    name: str
    folder: str
    igdb_slug: str | None
    moby_slug: str | None
    ss_id: int | None
    launchbox_id: int | None
    hasheous_id: int | None
    ra_id: int | None
    flashpoint_id: int | None
    hltb_slug: str | None


if __name__ == "__main__":
    supported_platforms: dict[str, SupportedPlatform] = {}

    for upl in UniversalPlatformSlug:
        slug_lower = upl.value.lower()

        igdb_platform = meta_igdb_handler.get_platform(slug_lower)
        moby_platform = meta_moby_handler.get_platform(slug_lower)
        ss_platform = meta_ss_handler.get_platform(slug_lower)
        launchbox_platform = meta_launchbox_handler.get_platform(slug_lower)
        hasheous_platform = meta_hasheous_handler.get_platform(slug_lower)
        ra_platform = meta_ra_handler.get_platform(slug_lower)
        flashpoint_platform = meta_flashpoint_handler.get_platform(slug_lower)
        hltb_platform = meta_hltb_handler.get_platform(slug_lower)

        supported_platforms[slug_lower] = {
            "name": igdb_platform.get("name", None)
            or moby_platform.get("name", None)
            or ss_platform.get("name", None)
            or launchbox_platform.get("name", None)
            or hasheous_platform.get("name", None)
            or ra_platform.get("name", None)
            or flashpoint_platform.get("name", None)
            or hltb_platform.get("name", None)
            or slug_lower.replace("-", " ").title(),
            "folder": slug_lower,
            "igdb_slug": igdb_platform.get("igdb_slug", None),
            "moby_slug": moby_platform.get("moby_slug", None),
            "ss_id": ss_platform["ss_id"],
            "launchbox_id": launchbox_platform["launchbox_id"],
            "hasheous_id": hasheous_platform["hasheous_id"],
            "ra_id": ra_platform["ra_id"],
            "flashpoint_id": flashpoint_platform["flashpoint_id"],
            "hltb_slug": hltb_platform.get("hltb_slug", None),
        }

    # Sort platforms by name field
    supported_platforms = dict(
        sorted(supported_platforms.items(), key=lambda item: item[1]["name"].lower())
    )

    print(
        """|Platform Name|Folder Name|Metadata Providers|
|---|---|---|"""
    )

    for platform in supported_platforms.values():
        print(
            f'| {platform["name"]} |',
            f'`{platform["folder"]}` |',
            (
                f'<a href="https://www.igdb.com/platforms/{platform["igdb_slug"]}" target="_blank" rel="noopener noreferrer"><img alt="igdb logo" src="../../resources/metadata_providers/igdb.png" height="24px" width="24px"></a>'
                if platform["igdb_slug"]
                else ""
            ),
            (
                f'<a href="https://www.screenscraper.fr/systemeinfos.php?plateforme={platform["ss_id"]}" target="_blank" rel="noopener noreferrer"><img alt="screenscraper logo" src="../../resources/metadata_providers/ss.png" height="24px" width="24px"></a>'
                if platform["ss_id"]
                else ""
            ),
            (
                f'<a href="https://www.mobygames.com/platform/{platform["moby_slug"]}" target="_blank" rel="noopener noreferrer"><img alt="mobygames logo" src="../../resources/metadata_providers/moby.png" height="24px" width="24px"></a>'
                if platform["moby_slug"]
                else ""
            ),
            (
                f'<a href="https://gamesdb.launchbox-app.com/platforms/games/{platform["launchbox_id"]}" target="_blank" rel="noopener noreferrer"><img alt="launchbox logo" src="../../resources/metadata_providers/launchbox.png" height="24px" width="24px"></a>'
                if platform["launchbox_id"]
                else ""
            ),
            (
                f'<a href="https://hasheous.org/index.html?page=dataobjectdetail&type=platform&id={platform["hasheous_id"]}" target="_blank" rel="noopener noreferrer"><img alt="hasheous logo" src="../../resources/metadata_providers/hasheous.png" height="24px" width="24px"></a>'
                if platform["hasheous_id"]
                else ""
            ),
            (
                f'<a href="https://retroachievements.org/system/{platform["ra_id"]}/games" target="_blank" rel="noopener noreferrer"><img alt="retroachivements logo" src="../../resources/metadata_providers/ra.png" height="24px" width="24px"></a>'
                if platform["ra_id"]
                else ""
            ),
            (
                f'<a href="https://flashpoint-project.org/platforms/{platform["flashpoint_id"]}" target="_blank" rel="noopener noreferrer"><img alt="flashpoint logo" src="../../resources/metadata_providers/flashpoint.png" height="24px" width="24px"></a>'
                if platform["flashpoint_id"]
                else ""
            ),
            (
                '<img alt="howlongtobeat logo" src="../../resources/metadata_providers/hltb.png" height="24px" width="24px">'
                if platform["hltb_slug"]
                else ""
            ),
            " |",
        )
