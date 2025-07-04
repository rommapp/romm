# uv run python3 -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST
from handler.metadata.launchbox_handler import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST

IGDB_SLUG_TO_MOBY_SLUG = {
    "bbcmicro": "bbc-micro",
    "astrocade": "bally-astrocade",
    "blu-ray-player": "blu-ray-disc-player",
    "amazon-fire-tv": "fire-os",
    "acpc": "cpc",
    "appleii": "apple-ii",
    "apple-iigs": "apple-iigs",
    "atari2600": "atari-2600",
    "atari5200": "atari-5200",
    "atari7800": "atari-7800",
    "atari8bit": "atari-8-bit",
    "acorn-archimedes": "acorn-32-bit",
    "acorn-electron": "electron",
    "c16": "commodore-16-plus4",
    "commodore-cdtv": "cdtv",
    "cpet": "pet",
    "c-plus-4": "commodore-16-plus4",
    "dc": "dreamcast",
    "fm-towns": "fmtowns",
    "fairchild-channel-f": "channel-f",
    "game-dot-com": "game-com",
    "gb": "gameboy",
    "gbc": "gameboy-color",
    "gba": "gameboy-advance",
    "leapster-explorer-slash-leadpad-explorer": "leapfrog-explorer",
    "mac": "macintosh",
    "microvision--1": "microvision",
    "ngc": "gamecube",
    "nds": "nintendo-ds",
    "neogeomvs": "neo-geo",
    "neogeoaes": "neo-geo",
    "win": "windows",
    "onlive-game-system": "onlive",
    "odyssey-2-slash-videopac-g7000": "odyssey-2",
    "odyssey--1": "odyssey",
    "pc-8800-series": "pc88",
    "pc-9800-series": "pc98",
    "palm-os": "palmos",
    "philips-cd-i": "cd-i",
    "ps": "playstation",
    "ps4--1": "playstation-4",
    "ps5": "playstation-5",
    "psvita": "ps-vita",
    "sega32x": "sega-32x",
    "segacd": "sega-cd",
    "g-and-w": "dedicated-handheld",
    "gamegear": "game-gear",
    "genesis-slash-megadrive": "genesis",
    "saturn": "sega-saturn",
    "x1": "sharp-x1",
    "sinclair-zx81": "zx81",
    "trs-80-color-computer": "trs-80-coco",
    "ti-994a": "ti-994a",
    "thomson-mo5": "thomson-mo",
    "turbografx16--1": "turbo-grafx",
    "turbografx-16-slash-pc-engine-cd": "turbografx-cd",
    "virtualboy": "virtual-boy",
    "wiiu": "wii-u",
    "series-x-s": "xbox-series",
    "ios": "iphone",
    "windows-mobile": "windowsphone",
    "winphone": "windows-phone",
    "xboxone": "xbox-one",
}


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
        moby_slug = plt["slug"] if plt["slug"] in MOBYGAMES_PLATFORM_LIST else None
        moby_slug = IGDB_SLUG_TO_MOBY_SLUG.get(plt["slug"], moby_slug)

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
