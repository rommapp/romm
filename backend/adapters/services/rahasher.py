import asyncio
import re

from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log

RAHASHER_VALID_HASH_REGEX = re.compile(r"[0-9a-f]{32}")


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
