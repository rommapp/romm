# poetry_npm run python3 -m scripts.generate_supported_platforms

from handler.metadata_handler.igdb_handler import IGDB_PLATFORM_LIST
from handler.metadata_handler.moby_handler import SLUG_TO_MOBY_ID

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
    "series-x": "xbox-series",
    "ios": "iphone",
    "windows-mobile": "windowsphone",
    "winphone": "windows-phone",
    "xboxone": "xbox-one",
}

if __name__ == "__main__":
    supported_platforms = {}
    matched_moby_slugs = []

    for platform in IGDB_PLATFORM_LIST:
        moby_slug = platform["slug"] if platform["slug"] in SLUG_TO_MOBY_ID else None
        moby_slug = IGDB_SLUG_TO_MOBY_SLUG.get(platform["slug"], moby_slug)
        supported_platforms[platform["name"]] = {
            "name": platform["name"],
            "igdb_slug": platform["slug"],
            "moby_slug": moby_slug,
        }
        if moby_slug:
            matched_moby_slugs.append(moby_slug)

    # Now go over the moby ids
    for slug, platform in SLUG_TO_MOBY_ID.items():
        if (
            platform["name"] not in supported_platforms
            and platform["name"].lower() not in supported_platforms
            and slug not in matched_moby_slugs
        ):
            supported_platforms[platform["name"]] = {
                "name": platform["name"],
                "igdb_slug": None,
                "moby_slug": slug,
            }

    # Sort platforms by key
    supported_platforms = dict(sorted(supported_platforms.items()))

    print("Below is a list of all supported platforms/systems/consoles and their respective folder names. **The folder name is case-sensitive and must be used exactly as it appears in the list below.**")
    print("\n")
    print("|Platform Name|Folder Name|IGDB|Mobygames|")
    print("|---|---|---|---|")

    for platform in supported_platforms.values():
        print(
            f'{platform["name"]} |',
            f'`{platform["igdb_slug"] or platform["moby_slug"]}` |',
            f'<a href="https://www.igdb.com/platforms/{platform["igdb_slug"]}" target="_blank" rel="noopener norefer">IGDB</a>|'
            if platform["igdb_slug"]
            else " |",
            f'<a href="https://www.mobygames.com/platform/{platform["moby_slug"]}" target="_blank" rel="noopener norefer">Mobygames</a>'
            if platform["moby_slug"]
            else " |",
        )
