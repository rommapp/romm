# poetry run python3 -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata.base_hander import UNIVERSAL_PLATFORM_SLUGS
from handler.metadata.igdb_handler import SLUG_TO_IGDB_PLATFORM
from handler.metadata.moby_handler import SLUG_TO_MOBY_PLATFORM


class SupportedPlatform(TypedDict):
    slug: str
    name: str
    igdb_slug: str | None
    moby_slug: str | None


if __name__ == "__main__":
    supported_platforms: dict[str, SupportedPlatform] = {}

    for slug in UNIVERSAL_PLATFORM_SLUGS:
        igdb_info = SLUG_TO_IGDB_PLATFORM.get(slug)
        moby_info = SLUG_TO_MOBY_PLATFORM.get(slug)
        supported_platforms[slug] = SupportedPlatform(
            {
                "slug": slug,
                "name": (igdb_info["name"] if igdb_info else None)
                or (moby_info["name"] if moby_info else None)
                or slug,
                "igdb_slug": igdb_info["igdb_slug"] if igdb_info else None,
                "moby_slug": moby_info["moby_slug"] if moby_info else None,
            }
        )

    # Sort platforms by key
    supported_platforms = dict(sorted(supported_platforms.items()))

    print(
        "Below is a list of all supported platforms/systems/consoles and their respective folder names. **The folder name is case-sensitive and must be used exactly as it appears in the list below.**"
    )
    print("\n")
    print("|Platform Name|Folder Name|IGDB|Mobygames|")
    print("|---|---|---|---|")

    for platform in supported_platforms.values():
        print(
            f'{platform["name"]} |',
            f'`{platform["slug"]}` |',
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
        )
