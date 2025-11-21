import asyncio
import re

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log

RAHASHER_VALID_HASH_REGEX = re.compile(r"[0-9a-f]{32}")

PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID: dict[UPS, int] = {
    UPS._3DO: 43,
    UPS.ACPC: 37,
    UPS.APPLEII: 38,
    UPS.ARCADE: 27,
    UPS.ARCADIA_2001: 73,
    UPS.ARDUBOY: 71,
    UPS.ATARI_JAGUAR_CD: 77,
    UPS.ATARI2600: 25,
    UPS.ATARI7800: 51,
    UPS.COLECOVISION: 44,
    UPS.DC: 40,
    UPS.ELEKTOR: 75,
    UPS.FAIRCHILD_CHANNEL_F: 57,
    UPS.FAMICOM: 7,
    UPS.GAMEGEAR: 15,
    UPS.GB: 4,
    UPS.GBA: 5,
    UPS.GBC: 6,
    UPS.GENESIS: 1,
    UPS.INTELLIVISION: 45,
    UPS.INTERTON_VC_4000: 74,
    UPS.JAGUAR: 17,
    UPS.LYNX: 13,
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: 69,
    UPS.MSX: 29,
    UPS.N64: 2,
    UPS.NDS: 18,
    UPS.NEO_GEO_CD: 56,
    UPS.NEO_GEO_POCKET: 14,
    UPS.NEO_GEO_POCKET_COLOR: 14,
    UPS.NES: 7,
    UPS.NGC: 16,
    UPS.NINTENDO_DSI: 78,
    UPS.ODYSSEY_2: 23,
    UPS.PC_8000: 47,
    UPS.PC_8800_SERIES: 47,
    UPS.PC_FX: 49,
    UPS.POKEMON_MINI: 24,
    UPS.PSX: 12,
    UPS.PS2: 21,
    UPS.PSP: 41,
    UPS.SATURN: 39,
    UPS.SEGACD: 9,
    UPS.SEGA32: 10,
    UPS.SFAM: 3,
    UPS.SG1000: 33,
    UPS.SMS: 11,
    UPS.SNES: 3,
    UPS.TURBOGRAFX_CD: 76,
    UPS.TG16: 8,
    UPS.UZEBOX: 80,
    UPS.VECTREX: 46,
    UPS.VIRTUALBOY: 28,
    UPS.WASM_4: 72,
    UPS.SUPERVISION: 63,
    UPS.WIN: 102,
    UPS.WONDERSWAN: 53,
    UPS.WONDERSWAN_COLOR: 53,
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
