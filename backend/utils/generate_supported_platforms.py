# poetry run python3 -m utils.generate_supported_platforms
from typing import TypedDict

from handler.metadata.base_hander import UniversalPlatformSlug
from handler.metadata.igdb_handler import SLUG_TO_IGDB_PLATFORM
from handler.metadata.moby_handler import SLUG_TO_MOBY_PLATFORM
from handler.metadata.ss_handler import SLUG_TO_SS_PLATFORM


class SupportedPlatform(TypedDict):
    slug: str
    name: str
    igdb_slug: str | None
    moby_slug: str | None
    ss_id: int | None


if __name__ == "__main__":
    supported_platforms: dict[str, SupportedPlatform] = {}

    for slug in UniversalPlatformSlug:
        igdb_info = SLUG_TO_IGDB_PLATFORM.get(slug)
        moby_info = SLUG_TO_MOBY_PLATFORM.get(slug)
        ss_info = SLUG_TO_SS_PLATFORM.get(slug)
        supported_platforms[slug] = SupportedPlatform(
            {
                "slug": slug,
                "name": (igdb_info["name"] if igdb_info else None)
                or (moby_info["name"] if moby_info else None)
                or (ss_info["name"] if ss_info else None)
                or slug.capitalize(),
                "igdb_slug": igdb_info["igdb_slug"] if igdb_info else None,
                "moby_slug": moby_info["moby_slug"] if moby_info else None,
                "ss_id": ss_info["id"] if ss_info else None,
            }
        )

    # Sort platforms by key
    supported_platforms = dict(sorted(supported_platforms.items()))

    with open("supported_platforms.md", "w") as f:
        f.write(
            "Below is a list of all supported platforms/systems/consoles and their respective folder names. **The folder name is case-sensitive and must be used exactly as it appears in the list below.**"
        )
        f.write("\n")
        f.write("\n")
        f.write("|Platform Name|Folder Name|IGDB|Mobygames|ScreenScraper|\n")
        f.write("|---|---|---|---|---|\n")

        for platform in supported_platforms.values():
            f.write(
                f"""{platform["name"]} | `{platform["slug"]}` | {f'<a href="https://www.igdb.com/platforms/{platform["igdb_slug"]}" target="_blank" rel="noopener norefer">IGDB</a>|'
                if platform["igdb_slug"]
                else " |"} {f'<a href="https://www.mobygames.com/platform/{platform["moby_slug"]}" target="_blank" rel="noopener norefer">Mobygames</a>|'
                if platform["moby_slug"]
                else " |"} {f'<a href="https://screenscraper.fr/systemeinfos.php?plateforme={platform["ss_id"]}" target="_blank" rel="noopener norefer">ScreenScraper</a>|'
                if platform["ss_id"]
                else " |"}\n"""
            )
