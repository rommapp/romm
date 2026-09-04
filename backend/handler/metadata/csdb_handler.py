"""CSDb metadata — C64 stills when Demozoo has none.

Public XML webservice, ID only (no search). Match via filename
``(csdb-75330)``, Edit-ROM paste, or Demozoo ``CsdbRelease``.
Never scrape ``csdb.dk/search/`` or release HTML.
https://csdb.dk/webservice/
"""

from __future__ import annotations

import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import parse_qs, urlparse

import httpx
from defusedxml import ElementTree as ET
from fastapi import HTTPException, status

from config import CSDB_API_ENABLED
from logger.logger import log
from utils import get_version, int_or_none
from utils.rate_limiter import RateLimiter

from .base_handler import BaseRom, MetadataHandler
from .demozoo_handler import build_scene_summary, http_url

CSDB_TAG_REGEX = re.compile(r"\(csdb-(\d+)\)", re.IGNORECASE)
CSDB_WEBSERVICE: Final[str] = "https://csdb.dk/webservice/"
CSDB_RELEASE_PAGE: Final[str] = "https://csdb.dk/release/?id={id}"
_rate_limiter = RateLimiter(1.5)


class CsdbCredit(TypedDict, total=False):
    name: str
    role: str


class CsdbMetadata(TypedDict, total=False):
    types: list[str]
    groups: list[str]
    platforms: list[str]
    credits: list[CsdbCredit]
    csdb_url: str | None
    first_release_date: int | None
    companies: list[str]
    genres: list[str]
    download_urls: list[str]


class CsdbRom(BaseRom):
    csdb_id: int | None
    csdb_metadata: NotRequired[CsdbMetadata]


def extract_csdb_id_from_filename(fs_name: str) -> int | None:
    match = CSDB_TAG_REGEX.search(fs_name)
    if match:
        return int_or_none(match.group(1))
    return None


def csdb_id_from_url(url: str) -> int | None:
    """Parse ``csdb.dk/release/?id=N`` from a Demozoo CsdbRelease link."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host != "csdb.dk":
        return None
    query = parse_qs(parsed.query)
    raw = (query.get("id") or [""])[0]
    if raw.isdigit():
        return int_or_none(raw)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "release" and parts[1].isdigit():
        return int_or_none(parts[1])
    return None


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    found = node.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _year_unix(year: str) -> int | None:
    if len(year) == 4 and year.isdigit():
        # 1 Jan UTC, same convention as other handlers' date fields.
        from datetime import datetime, timezone

        return int(datetime(int(year), 1, 1, tzinfo=timezone.utc).timestamp())
    return None


def production_from_xml(xml: str) -> CsdbRom:
    try:
        root = ET.fromstring(xml)
    except (ET.ParseError, ValueError):
        # defusedxml raises ValueError subclasses when it refuses entities.
        return CsdbRom(csdb_id=None)
    release = root.find("Release")
    if release is None:
        release = root.find(".//Release")
    if release is None:
        return CsdbRom(csdb_id=None)
    raw_id = _text(release, "ID")
    if not raw_id.isdigit():
        return CsdbRom(csdb_id=None)
    csdb_id = int(raw_id)
    name = _text(release, "Name")
    kind = _text(release, "Type")
    year = _text(release, "ReleaseYear")
    shot = http_url(_text(release, "ScreenShot")) or ""
    group = ""
    released_by = release.find("ReleasedBy")
    if released_by is not None:
        grp = released_by.find("Group")
        group = _text(grp, "Name") if grp is not None else ""
    credits: list[CsdbCredit] = []
    for credit in release.findall("Credits/Credit"):
        handle = credit.find("Handle")
        who = _text(handle, "Handle") if handle is not None else ""
        role = _text(credit, "CreditType")
        if who:
            credits.append(CsdbCredit(name=who, role=role))
    types = [kind] if kind else []
    groups = [group] if group else []
    csdb_url = CSDB_RELEASE_PAGE.format(id=csdb_id)
    screenshots = [shot] if shot else []
    metadata = CsdbMetadata(
        types=types,
        groups=groups,
        platforms=["C64"],
        credits=credits,
        csdb_url=csdb_url,
        first_release_date=_year_unix(year),
        companies=groups,
        genres=types,
        download_urls=[csdb_url],
    )
    return CsdbRom(
        csdb_id=csdb_id,
        name=name,
        summary=" · ".join(
            part
            for part in (
                build_scene_summary(
                    types=types,
                    who=group,
                    year=year,
                    party_lines=[],
                ),
                csdb_url,
            )
            if part
        ),
        url_cover=screenshots[0] if screenshots else "",
        url_screenshots=screenshots,
        csdb_metadata=metadata,
    )


class CsdbHandler(MetadataHandler):
    @classmethod
    def is_enabled(cls) -> bool:
        return CSDB_API_ENABLED

    async def _request(self, url: str) -> str:
        await _rate_limiter.acquire()
        headers = {
            "User-Agent": f"RomM/{get_version()}",
            "Accept": "application/xml, text/xml, */*",
        }
        try:
            body = await self._fetch_capped(url, headers=headers)
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning(
                "Can't connect to CSDb webservice", extra={"exception": str(exc)}
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to CSDb, check your internet connection",
            ) from exc
        if body is None:
            return ""
        return body.decode("utf-8", errors="replace")

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False
        try:
            xml = await self._request(
                f"{CSDB_WEBSERVICE}?type=release&id=75330&depth=1"
            )
        except Exception as exc:
            log.error("Error checking CSDb API: %s", exc)
            return False
        return "<Release>" in xml and "<ID>75330</ID>" in xml

    async def get_rom_by_id(self, csdb_id: int) -> CsdbRom:
        if not self.is_enabled() or not csdb_id:
            return CsdbRom(csdb_id=None)
        try:
            xml = await self._request(
                f"{CSDB_WEBSERVICE}?type=release&id={int(csdb_id)}&depth=2"
            )
        except HTTPException:
            return CsdbRom(csdb_id=None)
        return production_from_xml(xml)

    async def get_rom(self, fs_name: str, platform_slug: str) -> CsdbRom:
        """Filename ``(csdb-N)`` only. No title search — CSDb has none."""
        if not self.is_enabled():
            return CsdbRom(csdb_id=None)
        tagged = extract_csdb_id_from_filename(fs_name)
        if not tagged:
            return CsdbRom(csdb_id=None)
        log.debug("Found CSDb ID tag in filename: %s", tagged)
        rom = await self.get_rom_by_id(tagged)
        if rom.get("csdb_id"):
            return rom
        log.warning("CSDb ID %s from filename tag not found", tagged)
        return CsdbRom(csdb_id=None)
