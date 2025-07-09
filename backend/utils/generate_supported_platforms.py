# uv run python3 -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST
from handler.metadata.launchbox_handler import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST


class SupportedPlatform(TypedDict):
    name: str
    igdb_slug: str | None
    moby_slug: str | None
    ss_id: int | None
    launchbox_id: int | None


if __name__ == "__main__":
    supported_platforms: dict[str, SupportedPlatform] = {}
    matched_moby_slugs: list[str] = []
    matched_ss_ids: list[int] = []
    matched_launchbox_ids: list[int] = []

    for plt in IGDB_PLATFORM_LIST:
        moby_platform = MOBYGAMES_PLATFORM_LIST.get(plt["slug"])
        moby_slug = moby_platform["slug"] if moby_platform else None

        ss_platform = SCREENSAVER_PLATFORM_LIST.get(plt["slug"])
        ss_id = ss_platform["id"] if ss_platform else None

        launchbox_platform = LAUNCHBOX_PLATFORM_LIST.get(plt["slug"])
        launchbox_id = launchbox_platform["id"] if launchbox_platform else None

        supported_platforms[plt["name"]] = {
            "name": plt["name"],
            "igdb_slug": plt["slug"],
            "moby_slug": moby_slug,
            "ss_id": ss_id,
            "launchbox_id": launchbox_id,
        }
        if moby_slug:
            matched_moby_slugs.append(moby_slug)
        if ss_id:
            matched_ss_ids.append(ss_id)
        if launchbox_id:
            matched_launchbox_ids.append(launchbox_id)

    # Now go over the moby ids
    for slug, pltf in MOBYGAMES_PLATFORM_LIST.items():
        if (
            pltf["name"] not in supported_platforms
            and pltf["name"].lower() not in supported_platforms
            and slug not in matched_moby_slugs
        ):
            supported_platforms[pltf["name"]] = {
                "name": pltf["name"],
                "igdb_slug": None,
                "moby_slug": slug,
                "ss_id": None,
                "launchbox_id": None,
            }

    # And the remaining metadata sources
    for _slug, pltf in SCREENSAVER_PLATFORM_LIST.items():
        if (
            pltf["name"] not in supported_platforms
            and pltf["name"].lower() not in supported_platforms
            and pltf["id"] not in matched_ss_ids
        ):
            supported_platforms[pltf["name"]] = {
                "name": pltf["name"],
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": pltf["id"],
                "launchbox_id": None,
            }

    for _slug, pltf in LAUNCHBOX_PLATFORM_LIST.items():
        if (
            pltf["name"] not in supported_platforms
            and pltf["name"].lower() not in supported_platforms
            and pltf["id"] not in matched_launchbox_ids
        ):
            supported_platforms[pltf["name"]] = {
                "name": pltf["name"],
                "igdb_slug": None,
                "moby_slug": None,
                "ss_id": None,
                "launchbox_id": pltf["id"],
            }

    # Sort platforms by key
    supported_platforms = dict(sorted(supported_platforms.items()))

    print(
        "Below is a list of all supported platforms/systems/consoles and their respective folder names. **The folder name is case-sensitive and must be used exactly as it appears in the list below.**"
    )
    print("\n")
    print("|Platform Name|Folder Name|IGDB|Mobygames|ScreenSaver.fr|LaunchBox|")
    print("|---|---|---|---|")

    for platform in supported_platforms.values():
        print(
            f'{platform["name"]} |',
            f'`{platform["igdb_slug"] or platform["moby_slug"]}` |',
            (
                f'<a href="https://www.igdb.com/platforms/{platform["igdb_slug"]}" target="_blank" rel="noopener norefer">IGDB</a>|'
                if platform["igdb_slug"]
                else " |"
            ),
            (
                f'<a href="https://www.mobygames.com/platform/{platform["moby_slug"]}" target="_blank" rel="noopener norefer">Mobygames</a>'
                if platform["moby_slug"]
                else " |"
            ),
            (
                f'<a href="https://www.screenscraper.fr/systemeinfos.php?plateforme={platform["ss_id"]}" target="_blank" rel="noopener norefer">ScreenSaver.fr</a>'
                if platform["ss_id"]
                else " |"
            ),
            (
                f'<a href="https://gamesdb.launchbox-app.com/platforms/games/{platform["launchbox_id"]}" target="_blank" rel="noopener norefer">LaunchBox</a>'
                if platform["launchbox_id"]
                else " |"
            ),
        )
