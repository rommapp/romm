import asyncio
from typing import Final

from adapters.services.sigil import SigilExtractionResult
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import SaveTargetLayout
from utils import switch
from utils.nup import NupError, read_header
from utils.platform_slugs import UniversalPlatformSlug as UPS

# NUP package kinds in sigil's Switch content type terms.
NUP_CONTENT_TYPES: Final[dict[str, str]] = {
    "base": "application",
    "update": "patch",
    "addon": "addon",
    "addon_update": "addon",
}


class NupService:
    """Reads title ids from NUP containers, decrypted Switch dumps sigil can't open."""

    async def extract_title_id(
        self,
        platform_slug: str,
        file_path: str,
    ) -> SigilExtractionResult | None:
        try:
            header = await asyncio.to_thread(read_header, file_path)
        except (NupError, OSError) as exc:
            log.debug(f"No title id read from NUP {hl(file_path)}: {exc}")
            return None

        primary = header.primary
        if platform_slug == UPS.SWITCH and header.is_switch2:
            log.warning(
                f"{hl(file_path)} holds Switch 2 title {hl(primary.title_id)} "
                "but sits in the Switch folder"
            )

        return SigilExtractionResult(
            title_id=primary.title_id,
            # Switch saves are keyed by the base game's id.
            save_target=switch.derive_base_title_id(primary.title_id)
            or primary.title_id,
            usage=SaveTargetLayout.FOLDER_EXACT.value,
            content_type=NUP_CONTENT_TYPES.get(primary.kind),
            version=header.effective_version,
        )
