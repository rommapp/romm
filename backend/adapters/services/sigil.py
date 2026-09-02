import asyncio
from dataclasses import dataclass
from typing import Final

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log

try:
    import sigil
except ImportError:
    sigil = None  # type: ignore[assignment]
    log.debug("sigil binding not installed, title id extraction disabled")

# The Switch family needs prod.keys to decrypt headers, and is the only family
# whose files may have their title id embedded in the filename.
SWITCH_PLATFORM_SLUGS: Final = frozenset({UPS.SWITCH, UPS.SWITCH_2})

SIGIL_PLATFORM_SLUGS: Final[dict[str, str]] = {
    UPS.PSP: "psp",
    UPS.PSX: "psx",
    UPS.PS2: "ps2",
    UPS.PSVITA: "psvita",
    UPS.SWITCH: "switch",
    UPS.SWITCH_2: "switch",
    UPS.N3DS: "3ds",
    UPS.WII: "wii",
    UPS.WIIU: "wiiu",
    UPS.NGC: "gamecube",
    UPS.DC: "dreamcast",
    UPS.PS3: "ps3",
    UPS.XBOX: "xbox",
    UPS.XBOX360: "xbox360",
}

# Errors that are expected for arbitrary library files (no title id present,
# format sigil can't parse, missing decryption keys). Logged at debug level.
ROUTINE_SIGIL_ERROR_CODES: Final = frozenset(
    {"NOT_FOUND", "UNSUPPORTED", "UNSUPPORTED_FORMAT", "NEEDS_KEY"}
)


@dataclass(frozen=True)
class SigilExtractionResult:
    title_id: str
    save_target: str
    usage: str
    content_type: str | None = None
    version: int | None = None


class SigilService:
    """Service to extract platform-native title ids from ROM binaries via the
    optional `sigil` cffi binding."""

    async def extract_title_id(
        self,
        platform_slug: str,
        file_path: str,
    ) -> SigilExtractionResult | None:
        if sigil is None:
            return None

        sigil_slug = SIGIL_PLATFORM_SLUGS.get(platform_slug)
        if sigil_slug is None:
            return None

        try:
            result = await asyncio.to_thread(
                sigil.extract, file_path, platform=sigil_slug, filename_fallback=False
            )
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in ROUTINE_SIGIL_ERROR_CODES:
                log.debug(f"Sigil found no title id for {file_path}: {code}")
            else:
                log.error(f"Sigil extraction failed for {file_path}: {exc}")
            return None

        raw_content_type = getattr(result, "switch_content_type", None)
        content_type = (
            raw_content_type if raw_content_type not in (None, "", "unknown") else None
        )

        return SigilExtractionResult(
            title_id=result.title_id,
            # sigil calls this save_id; RomM's name for it is save_target.
            save_target=result.save_id,
            usage=result.usage,
            content_type=content_type,
            # Version 0 is a valid base-game version, so keep the int as-is;
            # a missing field (non-Switch, older binding) maps to None.
            version=getattr(result, "title_version", None),
        )
