import asyncio
import re

from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log

RAHASHER_VALID_HASH_REGEX = re.compile(r"[0-9a-f]{32}")

PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID: dict[str, int] = {
    "3do": 43,
    "acpc": 37,
    "appleii": 38,
    "arcade": 27,
    "arcadia-2001": 73,
    "arduboy": 71,
    "atari-jaguar-cd": 77,
    "atari2600": 25,
    "atari7800": 51,
    "colecovision": 44,
    "dc": 40,
    "elektor": 75,
    "fairchild-channel-f": 57,
    "famicom": 7,
    "gamegear": 15,
    "gb": 4,
    "gba": 5,
    "gbc": 6,
    "genesis": 1,
    "intellivision": 45,
    "interton-vc-4000": 74,
    "jaguar": 17,
    "lynx": 13,
    "mega-duck-slash-cougar-boy": 69,
    "msx": 29,
    "n64": 2,
    "nds": 18,
    "neo-geo-cd": 56,
    "neo-geo-pocket": 14,
    "neo-geo-pocket-color": 14,
    "nes": 7,
    "ngc": 16,
    "nintendo-dsi": 78,
    "odyssey-2": 23,
    "pc-8800-series": 47,
    "pc-fx": 49,
    "pokemon-mini": 24,
    "psx": 12,
    "ps2": 21,
    "psp": 41,
    "saturn": 39,
    "segacd": 9,
    "sega32": 10,
    "sfam": 3,
    "sg1000": 33,
    "sms": 11,
    "snes": 3,
    "turbografx-cd": 76,
    "tg16": 8,
    "uzebox": 80,
    "vectrex": 46,
    "virtual-boy": 28,
    "virtualboy": 28,
    "wasm-4": 72,
    "watara-slash-quickshot-supervision": 63,
    "win": 102,
    "wonderswan": 53,
    "wonderswan-color": 53,
}


class RAHasherError(Exception): ...


class RAHasherService:
    """Service to calculate RetroAchievements hashes using RAHasher."""

    async def calculate_hash(self, platform_id: int, file_path: str) -> str:
        from handler.metadata.ra_handler import RA_ID_TO_SLUG

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
