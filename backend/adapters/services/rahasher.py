import asyncio
import re
from pathlib import Path

from logger.logger import log

RAHASHER_VALID_HASH_REGEX = re.compile(r"^[0-9a-f]{32}$")

# TODO: Centralize standarized platform slugs using StrEnum.
PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID: dict[str, int] = {
    "3do": 43,
    "cpc": 37,
    "acpc": 37,
    "apple2": 38,
    "arcade": 27,
    "arcadia": 73,
    "arduboy": 71,
    "atari2600": 25,
    "atari7800": 51,
    "jaguarcd": 77,
    "colecovision": 44,
    "dreamcast": 40,
    "gb": 4,
    "gba": 5,
    "gbc": 6,
    "gamegear": 15,
    "genesis": 1,
    "intellivision": 45,
    "jaguar": 17,
    "lynx": 13,
    "msx": 29,
    "megaduck": 69,
    "megadrive": 16,
    "nes": 7,
    "ngc": 14,
    "famicom": 7,
    "neogeocd": 56,
    "ngp": 14,
    "ngpc": 14,
    "n64": 2,
    "nds": 18,
    "dsi": 78,
    "odyssey2": 23,
    "pc88": 47,
    "pcfx": 49,
    "psp": 41,
    "playstation": 12,
    "psx": 12,
    "ps2": 21,
    "pokemini": 24,
    "saturn": 39,
    "sega-32x": 10,
    "sega32": 10,
    "sega-cd": 9,
    "segacd": 9,
    "sega-master-system": 11,
    "sms": 11,
    "sg-1000": 33,
    "snes": 3,
    "turbografx-cd": 76,
    "turbografx-16-slash-pc-engine-cd": 76,
    "turbo-grafx": 8,
    "turbografx16--1": 8,
    "vectrex": 26,
    "virtual-boy": 28,
    "virtualboy": 28,
    "watara-slash-quickshot-supervision": 63,
    "wonderswan": 53,
    "wonderswan-color": 53,
}


class RAHasherError(Exception): ...


class RAHasherService:
    """Service to calculate RetroAchievements hashes using RAHasher."""

    async def calculate_hash(self, platform_slug: str, file_path: Path) -> str:
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID.get(platform_slug)
        if not platform_id:
            raise RAHasherError(
                f"Platform not supported by RetroAchievements. {platform_slug=}"
            )

        args = (str(platform_id), str(file_path))
        log.debug("Executing RAHasher with args: %s", args)

        proc = await asyncio.create_subprocess_exec(
            "RAHasher",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return_code = await proc.wait()
        if return_code != 1:
            if proc.stderr is not None:
                stderr = (await proc.stderr.read()).decode("utf-8")
            else:
                stderr = None
            raise RAHasherError(f"RAHasher failed with code {return_code}. {stderr=}")

        if proc.stdout is None:
            raise RAHasherError("RAHasher did not return a hash.")

        file_hash = (await proc.stdout.read()).decode("utf-8").strip()
        if not file_hash:
            raise RAHasherError(
                f"RAHasher returned an empty hash. {platform_id=}, {file_path=}"
            )
        if not RAHASHER_VALID_HASH_REGEX.match(file_hash):
            raise RAHasherError(
                f"RAHasher returned an invalid hash: {file_hash=}, {platform_id=}, {file_path=}"
            )

        return file_hash
