import asyncio
import re

from handler.metadata.ra_handler import RA_ID_TO_SLUG
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log

RAHASHER_VALID_HASH_REGEX = re.compile(r"[0-9a-f]{32}")

# TODO: Centralize standarized platform slugs using StrEnum.
PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID: dict[str, int] = {
    "3do": 43,
    "cpc": 37,
    "acpc": 37,
    "apple2": 38,
    "appleii": 38,
    "arcade": 27,
    "arcadia-2001": 73,
    "arduboy": 71,
    "atari-2600": 25,
    "atari2600": 25,
    "atari-7800": 51,
    "atari7800": 51,
    "atari-jaguar-cd": 77,
    "colecovision": 44,
    "dreamcast": 40,
    "dc": 40,
    "gameboy": 4,
    "gb": 4,
    "gameboy-advance": 5,
    "gba": 5,
    "gameboy-color": 6,
    "gbc": 6,
    "game-gear": 15,
    "gamegear": 15,
    "gamecube": 16,
    "ngc": 14,
    "genesis": 1,
    "genesis-slash-megadrive": 16,
    "intellivision": 45,
    "jaguar": 17,
    "lynx": 13,
    "msx": 29,
    "mega-duck-slash-cougar-boy": 69,
    "nes": 7,
    "famicom": 7,
    "neo-geo-cd": 56,
    "neo-geo-pocket": 14,
    "neo-geo-pocket-color": 14,
    "n64": 2,
    "nintendo-ds": 18,
    "nds": 18,
    "nintendo-dsi": 78,
    "odyssey-2": 23,
    "pc-8000": 47,
    "pc-8800-series": 47,
    "pc-fx": 49,
    "psp": 41,
    "playstation": 12,
    "ps": 12,
    "ps2": 21,
    "pokemon-mini": 24,
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

    async def calculate_hash(self, platform_id: int, file_path: str) -> str:
        log.debug(
            f"Executing {hl('RAHasher', color=LIGHTMAGENTA)} for platform: {hl(RA_ID_TO_SLUG[platform_id])} - file: {hl(file_path.split('/')[-1])}"
        )
        args = (str(platform_id), file_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                "RAHasher",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            log.error("RAHasher executable not found in PATH")
            return ""

        return_code = await proc.wait()
        if return_code != 1:
            if proc.stderr is not None:
                stderr = (await proc.stderr.read()).decode("utf-8")
            else:
                stderr = None
            log.error(f"RAHasher failed with code {return_code}. {stderr=}")
            return ""

        if proc.stdout is None:
            log.error("RAHasher did not return a hash.")
            return ""

        file_hash = (await proc.stdout.read()).decode("utf-8").strip()
        if not file_hash:
            log.error(
                f"RAHasher returned an empty hash for file {file_path} (platform ID: {platform_id})"
            )
            return ""

        match = RAHASHER_VALID_HASH_REGEX.search(file_hash)
        if not match:
            log.error(
                f"RAHasher returned invalid hash {file_hash} for file {file_path} (platform ID: {platform_id}"
            )
            return ""

        return match.group(0)
