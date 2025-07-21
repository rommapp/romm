# uv run python3 -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata.hasheous_handler import HASHEOUS_PLATFORM_LIST
from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST
from handler.metadata.launchbox_handler import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.ra_handler import RA_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST

# from handler.metadata.tgdb_handler import TGDB_PLATFORM_LIST


class SupportedPlatform(TypedDict):
    name: str
    folder: str
    igdb_slug: str | None
    moby_slug: str | None
    ss_id: int | None
    launchbox_id: int | None
    hasheous_id: int | None
    ra_id: int | None


if __name__ == "__main__":
    supported_platforms: dict[str, SupportedPlatform] = {}
    matched_moby_slugs: list[str] = []
    matched_ss_ids: list[int] = []
    matched_launchbox_ids: list[int] = []
    matched_hasheous_ids: list[int] = []
    matched_ra_ids: list[int] = []

    for plt in IGDB_PLATFORM_LIST.values():
        moby_platform = MOBYGAMES_PLATFORM_LIST.get(plt["slug"])
        moby_slug = moby_platform["slug"] if moby_platform else None

        ss_platform = SCREENSAVER_PLATFORM_LIST.get(plt["slug"])
        ss_id = ss_platform["id"] if ss_platform else None

        launchbox_platform = LAUNCHBOX_PLATFORM_LIST.get(plt["slug"])
        launchbox_id = launchbox_platform["id"] if launchbox_platform else None

        hasheous_platform = HASHEOUS_PLATFORM_LIST.get(plt["slug"])
        hasheous_id = hasheous_platform["id"] if hasheous_platform else None

        ra_platform = RA_PLATFORM_LIST.get(plt["slug"])
        ra_id = ra_platform["id"] if ra_platform else None

        supported_platforms[plt["slug"].lower()] = {
            "name": plt["name"],
            "folder": plt["slug"],
            "igdb_slug": plt["slug"],
            "moby_slug": moby_slug,
            "ss_id": ss_id,
            "launchbox_id": launchbox_id,
            "hasheous_id": hasheous_id,
            "ra_id": ra_id,
        }

        if moby_slug:
            matched_moby_slugs.append(moby_slug)
        if ss_id:
            matched_ss_ids.append(ss_id)
        if launchbox_id:
            matched_launchbox_ids.append(launchbox_id)
        if hasheous_id:
            matched_hasheous_ids.append(hasheous_id)
        if ra_id:
            matched_ra_ids.append(ra_id)

    # Now go over the moby ids
    for slug, mplt in MOBYGAMES_PLATFORM_LIST.items():
        if mplt["slug"] in matched_moby_slugs:
            continue

        # If the platform is not in supported_platforms, add it
        slug_lower = slug.lower()
        if slug_lower not in supported_platforms:
            supported_platforms[slug_lower] = {
                "name": mplt["name"],
                "folder": slug,
                "igdb_slug": None,
                "moby_slug": mplt["slug"],
                "ss_id": None,
                "launchbox_id": None,
                "hasheous_id": None,
                "ra_id": None,
            }
        # If the platform is already in supported_platforms, update the moby_slug if it's None
        elif supported_platforms[slug_lower]["moby_slug"] is None:
            supported_platforms[slug_lower]["moby_slug"] = mplt["slug"]

    # And the remaining metadata sources
    for slug, ssplt in SCREENSAVER_PLATFORM_LIST.items():
        if ssplt["id"] in matched_ss_ids:
            continue

        slug_lower = slug.lower()
        if slug_lower not in supported_platforms:
            supported_platforms[slug_lower] = {
                "name": ssplt["name"],
                "folder": slug,
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": ssplt["id"],
                "launchbox_id": None,
                "hasheous_id": None,
                "ra_id": None,
            }
        elif supported_platforms[slug_lower]["ss_id"] is None:
            supported_platforms[slug_lower]["ss_id"] = ssplt["id"]

    for slug, lbplt in LAUNCHBOX_PLATFORM_LIST.items():
        if lbplt["id"] in matched_launchbox_ids:
            continue

        slug_lower = slug.lower()
        if slug_lower not in supported_platforms:
            supported_platforms[slug_lower] = {
                "name": lbplt["name"],
                "folder": slug,
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": None,
                "launchbox_id": lbplt["id"],
                "hasheous_id": None,
                "ra_id": None,
            }
        elif supported_platforms[slug_lower]["launchbox_id"] is None:
            supported_platforms[slug_lower]["launchbox_id"] = lbplt["id"]

    for slug, hsplt in HASHEOUS_PLATFORM_LIST.items():
        if hsplt["id"] in matched_hasheous_ids:
            continue

        slug_lower = slug.lower()
        if slug_lower not in supported_platforms:
            supported_platforms[slug_lower] = {
                "name": hsplt["name"],
                "folder": slug,
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": None,
                "launchbox_id": None,
                "hasheous_id": hsplt["id"],
                "ra_id": None,
            }
        elif supported_platforms[slug_lower]["hasheous_id"] is None:
            supported_platforms[slug_lower]["hasheous_id"] = hsplt["id"]

    for slug, raplt in RA_PLATFORM_LIST.items():
        if raplt["id"] in matched_ra_ids:
            continue

        slug_lower = slug.lower()
        if slug_lower not in supported_platforms:
            supported_platforms[slug_lower] = {
                "name": raplt["name"],
                "folder": slug,
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": None,
                "launchbox_id": None,
                "hasheous_id": None,
                "ra_id": raplt["id"],
            }
        elif supported_platforms[slug_lower]["ra_id"] is None:
            supported_platforms[slug_lower]["ra_id"] = raplt["id"]

    # Sort platforms by name field
    supported_platforms = dict(
        sorted(supported_platforms.items(), key=lambda item: item[1]["name"].lower())
    )

    print(
        """<!-- vale off -->
<!-- prettier-ignore -->

Below is a list of all supported platforms/systems/consoles and their respective folder names. Supported platforms means RomM can fetch metadata from sources for those platforms.

!!! info
    For platforms that can be playable in the browser, please check [emulatorjs supported platforms](./EmulatorJS-Player.md) and [ruffle player](./RuffleRS-Player.md).

!!! danger
    **The folder name is case-sensitive and must be used exactly as it appears in the list below.**

|Platform Name|Folder Name|Metadata Providers|
|---|---|---|"""
    )

    for platform in supported_platforms.values():
        print(
            f'| {platform["name"]} |',
            f'`{platform["folder"]}` |',
            (
                f'<a href="https://www.igdb.com/platforms/{platform["igdb_slug"]}" target="_blank" rel="noopener norefer"><img alt="igdb logo" src="../../resources/metadata_providers/igdb.png" height="24px" width="24px"></a>'
                if platform["igdb_slug"]
                else ""
            ),
            (
                f'<a href="https://www.screenscraper.fr/systemeinfos.php?plateforme={platform["ss_id"]}" target="_blank" rel="noopener norefer"><img alt="screenscraper logo" src="../../resources/metadata_providers/ss.png" height="24px" width="24px"></a>'
                if platform["ss_id"]
                else ""
            ),
            (
                f'<a href="https://www.mobygames.com/platform/{platform["moby_slug"]}" target="_blank" rel="noopener norefer"><img alt="mobygames logo" src="../../resources/metadata_providers/moby.png" height="24px" width="24px"></a>'
                if platform["moby_slug"]
                else ""
            ),
            (
                f'<a href="https://gamesdb.launchbox-app.com/platforms/games/{platform["launchbox_id"]}" target="_blank" rel="noopener norefer"><img alt="launchbox logo" src="../../resources/metadata_providers/launchbox.png" height="24px" width="24px"></a>'
                if platform["launchbox_id"]
                else ""
            ),
            (
                f'<a href="https://hasheous.org/index.html?page=dataobjectdetail&type=platform&id={platform["hasheous_id"]}" target="_blank" rel="noopener norefer"><img alt="hasheous logo" src="../../resources/metadata_providers/hasheous.png" height="24px" width="24px"></a>'
                if platform["hasheous_id"]
                else ""
            ),
            (
                f'<a href="https://retroachievements.org/system/{platform["ra_id"]}/games" target="_blank" rel="noopener norefer"><img alt="retroachivements logo" src="../../resources/metadata_providers/ra.png" height="24px" width="24px"></a>'
                if platform["ra_id"]
                else ""
            ),
            " |",
        )

    print("\n<!-- vale on -->")
