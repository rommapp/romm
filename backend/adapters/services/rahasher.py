import asyncio
import re
from pathlib import Path

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.metadata.ra_handler import RAGamesPlatform
from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from utils.filesystem import COMPRESSED_FILE_EXTENSIONS

RAHASHER_VALID_HASH_REGEX = re.compile(r"[0-9a-f]{32}")

# Platforms whose hash algorithm requires an on-disk disc image
# (ISO9660/bin+cue/CHD). When the source file is an archive, RAHasher falls
# back to "buffer hash" mode which these consoles don't support, failing
# with "Unsupported console for buffer hash: <id>" after paying a full
# subprocess spawn.
RA_BUFFER_HASH_UNSUPPORTED: frozenset[UPS] = frozenset(
    {
        UPS.SEGACD,
        UPS.PSX,
        UPS.PS2,
        UPS.SATURN,
        UPS.DC,
        UPS.PSP,
        UPS._3DO,
        UPS.PC_FX,
        UPS.NEO_GEO_CD,
        UPS.TURBOGRAFX_CD,
        UPS.ATARI_JAGUAR_CD,
        UPS.WII,
    }
)

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
    UPS.WII: 19,
    UPS.WONDERSWAN: 53,
    UPS.WONDERSWAN_COLOR: 53,
}

RA_BUFFER_HASH_UNSUPPORTED_IDS: frozenset[int] = frozenset(
    PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[ups] for ups in RA_BUFFER_HASH_UNSUPPORTED
)


class RAHasherError(Exception): ...


class RAHasherService:
    """Service to calculate RetroAchievements hashes using RAHasher."""

    async def calculate_hash(self, platform: RAGamesPlatform, file_path: str) -> str:
        # Skip the subprocess entirely when the file is an archive and the
        # RA platform needs an on-disk disc image. RAHasher would just spawn,
        # fail with "Unsupported console for buffer hash: {id}", and return
        # nothing, so we'd pay process-spawn overhead per ROM for no result.
        if file_path.lower().endswith(tuple(COMPRESSED_FILE_EXTENSIONS)):
            if platform["ra_id"] in RA_BUFFER_HASH_UNSUPPORTED_IDS:
                log.debug(
                    f"Skipping {hl('RAHasher', color=LIGHTMAGENTA)} for archived "
                    f"{platform['slug']} file {hl(file_path)}: "
                    f"disc-based platforms don't support buffer hashing"
                )
                return ""

        # For folder-based multi-file ROMs the path ends with /*. RAHasher
        # cannot process compressed files via a glob — it fails with "Could not
        # open file". When the folder contains archives, switch to hashing the
        # largest archive directly (cartridge platforms support buffer hashing),
        # or skip entirely for disc platforms that don't.
        if file_path.endswith("/*"):
            folder = Path(file_path[:-2])

            def _find_archives() -> list[Path]:
                if not folder.is_dir():
                    return []
                return [
                    f
                    for f in folder.iterdir()
                    if f.is_file()
                    and f.name.lower().endswith(tuple(COMPRESSED_FILE_EXTENSIONS))
                ]

            archive_files = await asyncio.to_thread(_find_archives)
            if archive_files:
                if platform["ra_id"] in RA_BUFFER_HASH_UNSUPPORTED_IDS:
                    log.debug(
                        f"Skipping {hl('RAHasher', color=LIGHTMAGENTA)} for folder "
                        f"{hl(file_path)}: contains compressed files on disc-based platform"
                    )
                    return ""
                # Cartridge platform: buffer-hash the largest archive directly
                largest = await asyncio.to_thread(
                    max, archive_files, key=lambda f: f.stat().st_size
                )
                file_path = str(largest)

        log.debug(
            f"Executing {hl('RAHasher', color=LIGHTMAGENTA)} for platform: {hl(platform['slug'], color=LIGHTMAGENTA)} - file: {hl(file_path)}"
        )
        args = (str(platform["ra_id"]), file_path)

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
        if return_code != 0:
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
                f"RAHasher returned an empty hash for file {file_path} (platform ID: {platform['ra_id']})"
            )
            return ""

        match = RAHASHER_VALID_HASH_REGEX.search(file_hash)
        if not match:
            log.error(
                f"RAHasher returned invalid hash {file_hash} for file {file_path} (platform ID: {platform['ra_id']})"
            )
            return ""

        return match.group(0)
