import asyncio
from dataclasses import dataclass
from typing import Any, Final

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log

try:
    import sigil
except ImportError:
    sigil = None  # type: ignore[assignment]

SWITCH_SIGIL_SLUG: Final = "switch"

SIGIL_PLATFORM_SLUGS: Final[dict[UPS, str]] = {
    UPS.PSP: "psp",
    UPS.PSX: "psx",
    UPS.PS2: "ps2",
    UPS.PSVITA: "psvita",
    UPS.SWITCH: SWITCH_SIGIL_SLUG,
    UPS.SWITCH_2: SWITCH_SIGIL_SLUG,
    UPS.N3DS: "3ds",
    UPS.WII: "wii",
    UPS.WIIU: "wiiu",
    UPS.NGC: "gamecube",
}

# Errors that are expected for arbitrary library files (no title id present,
# format sigil can't parse, missing decryption keys). Logged at debug level.
ROUTINE_SIGIL_ERROR_CODES: Final = frozenset(
    {"NOT_FOUND", "UNSUPPORTED", "UNSUPPORTED_FORMAT", "NEEDS_KEY"}
)

_missing_binding_logged = False


class SigilServiceError(Exception): ...


@dataclass(frozen=True)
class SigilExtractionResult:
    title_id: str
    save_id: str
    usage: str


class SigilService:
    """Service to extract platform-native title ids from ROM binaries via the
    optional `sigil` cffi binding."""

    async def extract_title_id(
        self,
        platform_slug: UPS | str,
        file_path: str,
        prod_keys_path: str | None = None,
    ) -> SigilExtractionResult | None:
        global _missing_binding_logged

        if sigil is None:
            if not _missing_binding_logged:
                log.debug("sigil binding not installed, skipping title id extraction")
                _missing_binding_logged = True
            return None

        sigil_slug = SIGIL_PLATFORM_SLUGS.get(platform_slug)  # type: ignore[arg-type]
        if sigil_slug is None:
            return None

        kwargs: dict[str, Any] = {"platform": sigil_slug, "filename_fallback": False}
        if sigil_slug == SWITCH_SIGIL_SLUG:
            kwargs["prod_keys_path"] = prod_keys_path

        try:
            result = await asyncio.to_thread(sigil.extract, file_path, **kwargs)
        except Exception as exc:
            code = getattr(exc, "code", None)
            is_sigil_error = isinstance(exc, getattr(sigil, "SigilError", ()))
            if is_sigil_error and code in ROUTINE_SIGIL_ERROR_CODES:
                log.debug(f"Sigil found no title id for {file_path}: {code}")
            else:
                log.error(f"Sigil extraction failed for {file_path}: {exc}")
            return None

        return SigilExtractionResult(
            title_id=result.title_id,
            save_id=result.save_id,
            usage=result.usage,
        )
