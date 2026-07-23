import re
from typing import Final

from config import UPC_LOOKUP_API_KEY, UPC_LOOKUP_BASE_URL, UPC_LOOKUP_ENABLED
from logger.logger import log
from utils import get_version
from utils.context import ctx_httpx_client

from .base_handler import MetadataHandler

# Retail suffixes/noise commonly present in UPC-database product titles that hurt
# name matching against game-metadata providers (e.g. "Sonic - Nintendo Switch").
_TITLE_NOISE_RE = re.compile(
    r"\s*[-–(]?\s*(video ?game|nintendo switch|playstation \d?|"
    r"xbox(?: one| series [sx])?|pc|ntsc|pal|region free|brand new|sealed)\b.*$",
    re.IGNORECASE,
)


class UPCHandler(MetadataHandler):
    """Resolve a UPC/EAN/barcode to a product title via an external lookup service.

    This does not attach provider IDs; the resolved title is fed into the normal
    name-based scan so the existing providers do the actual game matching.
    """

    def __init__(self) -> None:
        self.base_url = UPC_LOOKUP_BASE_URL.rstrip("/")
        self.lookup_url = f"{self.base_url}/lookup"
        self.min_title_length: Final = 2

    @classmethod
    def is_enabled(cls) -> bool:
        return UPC_LOOKUP_ENABLED

    def _clean_title(self, title: str) -> str:
        cleaned = _TITLE_NOISE_RE.sub("", title).strip(" -–:")
        return cleaned or title.strip()

    async def resolve_upc_to_title(self, upc: str) -> str | None:
        """Return the best product title for a UPC, or None if unresolved."""
        if not self.is_enabled():
            log.warning("UPC lookup is disabled; cannot resolve barcode %s", upc)
            return None

        upc = upc.strip()
        if not upc:
            return None

        headers = {"User-Agent": f"RomM/{get_version()}"}
        if UPC_LOOKUP_API_KEY:
            headers["user_key"] = UPC_LOOKUP_API_KEY

        httpx_client = ctx_httpx_client.get()
        try:
            response = await httpx_client.get(
                self.lookup_url,
                params={"upc": upc},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log.warning("Failed to resolve UPC %s: %s", upc, e)
            return None

        items = data.get("items") or []
        for item in items:
            title = (item.get("title") or "").strip()
            if len(title) >= self.min_title_length:
                return self._clean_title(title)

        return None
