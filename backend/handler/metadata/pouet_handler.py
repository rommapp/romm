"""Pouët metadata for demoscene productions.

Match by production id (filename tag ``(pouet-N)`` or Edit-ROM paste), or by the
unique-title 302 from ``search.php?type=prod`` (Location ``which=N``).
Never parse ``prod.php`` HTML (ambiguous titles stay unmatched).
"""

from __future__ import annotations

import json
import re
from typing import Any, Final, NotRequired, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from config import POUET_API_ENABLED
from logger.logger import log
from utils import get_version, int_or_none
from utils.context import ctx_httpx_client
from utils.rate_limiter import RateLimiter

from .base_handler import BaseRom, MetadataHandler, unavailable
from .demozoo_handler import (
    DEMOZOO_PROD_PAGE,
    _append_unique,
    _youtube_id_from_url,
    build_scene_summary,
    format_credit_line,
    http_url,
)

POUET_TAG_REGEX = re.compile(r"\(pouet-(\d+)\)", re.IGNORECASE)
POUET_WHICH_RE = re.compile(r"which=(\d+)", re.IGNORECASE)
POUET_API_PROD: Final[str] = "https://api.pouet.net/v1/prod/"
POUET_PROD_PAGE: Final[str] = "https://www.pouet.net/prod.php?which={id}"
POUET_SEARCH_URL: Final[str] = "https://www.pouet.net/search.php"
_rate_limiter = RateLimiter(2.0)


class PouetCredit(TypedDict, total=False):
    name: str
    role: str


class PouetMetadata(TypedDict, total=False):
    types: list[str]
    groups: list[str]
    platforms: list[str]
    party: str | None
    invitation: str | None
    credits: list[PouetCredit]
    vote_avg: float | None
    pouet_rank: int | None
    pouet_cdc: int | None
    pouet_popularity: float | None
    demozoo_id: int | None
    pouet_url: str | None
    youtube_video_id: str | None
    soundtrack_urls: list[str]
    genres: list[str]
    companies: list[str]
    download_urls: list[str]


class PouetRom(BaseRom):
    pouet_id: int | None
    pouet_metadata: NotRequired[PouetMetadata]


def extract_pouet_id_from_filename(fs_name: str) -> int | None:
    """Extract Pouët ID from a filename tag like ``(pouet-99)``."""
    match = POUET_TAG_REGEX.search(fs_name)
    if match:
        return int_or_none(match.group(1))
    return None


def pouet_id_from_location(location: str) -> int | None:
    """Parse ``prod.php?which=N`` from a 302 Location. Never read HTML."""
    if not location:
        return None
    match = POUET_WHICH_RE.search(location)
    if match:
        return int_or_none(match.group(1))
    query = parse_qs(urlparse(location).query)
    which = query.get("which") or query.get("WHICH")
    if which and which[0].isdigit():
        return int_or_none(which[0])
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


_POUET_TYPE_LABELS: Final[dict[str, str]] = {
    "demo": "Demo",
    "64k": "64K Intro",
    "4k": "4K Intro",
    "intro": "Intro",
    "invitation": "Invitation",
    "withinv": "Invitation",
    "musicdisk": "Musicdisk",
    "diskmag": "Diskmag",
    "bbstro": "BBStro",
    "cracktro": "Cracktro",
    "game": "Game",
    "wild": "Wild",
    "procedural graphics": "Graphics",
}


def _normalize_pouet_types(prod: dict[str, Any]) -> list[str]:
    raw: list[str] = []
    for item in prod.get("types") or []:
        raw.append(str(item))
    if prod.get("type"):
        raw.insert(0, str(prod["type"]))
    out: list[str] = []
    for item in raw:
        for part in item.split(","):
            key = part.strip().lower()
            if not key:
                continue
            label = _POUET_TYPE_LABELS.get(key, part.strip().title())
            if label not in out:
                out.append(label)
    return out


def _party_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def production_to_rom(prod: dict[str, Any]) -> PouetRom:
    pouet_id = int(prod["id"])
    groups = [
        str(g["name"])
        for g in (prod.get("groups") or [])
        if isinstance(g, dict) and g.get("name")
    ]
    platforms: list[str] = []
    raw_platforms = prod.get("platforms") or {}
    if isinstance(raw_platforms, dict):
        for item in raw_platforms.values():
            if isinstance(item, dict) and item.get("name"):
                platforms.append(str(item["name"]))

    types = _normalize_pouet_types(prod)

    credits: list[PouetCredit] = []
    for row in prod.get("credits") or []:
        if not isinstance(row, dict):
            continue
        user = row.get("user") or {}
        name = user.get("nickname") if isinstance(user, dict) else ""
        role = str(row.get("role") or "").strip().title()
        if name:
            credits.append(PouetCredit(name=str(name), role=role))

    party_lines: list[str] = []
    party = _party_name(prod.get("party"))
    for row in prod.get("placings") or []:
        if not isinstance(row, dict):
            continue
        party_name = _party_name(row.get("party")) or party
        if party_name and not party:
            party = party_name
        line = party_name
        if row.get("year") and party_name and str(row["year"]) not in party_name:
            line = f"{party_name} {row['year']}"
        compo = str(row.get("compo_name") or "").strip()
        if compo:
            line = f"{line} / {compo}" if line else compo
        ranking = str(row.get("ranking") or "").strip()
        if ranking:
            line = f"{line} #{ranking}" if line else f"#{ranking}"
        if line and line not in party_lines:
            party_lines.append(line)
        if len(party_lines) >= 3:
            break
    if not party_lines and (prod.get("party_compo_name") or prod.get("party_place")):
        line = party
        if prod.get("party_year") and party and str(prod["party_year"]) not in party:
            line = f"{party} {prod['party_year']}"
        if prod.get("party_compo_name"):
            line = (
                f"{line} / {prod['party_compo_name']}"
                if line
                else str(prod["party_compo_name"])
            )
        if prod.get("party_place"):
            line = (
                f"{line} #{prod['party_place']}" if line else f"#{prod['party_place']}"
            )
        if line:
            party_lines.append(line)

    invitation = None
    invited = _party_name(prod.get("invitation"))
    if invited:
        year = str(prod.get("invitationyear") or "").strip()
        invitation = f"Invitation for {invited}" + (f" ({year})" if year else "")

    demozoo_id = None
    raw_dz = prod.get("demozoo")
    if raw_dz not in (None, "", "0", 0):
        demozoo_id = int_or_none(raw_dz)

    screenshots: list[str] = []
    shot = http_url(str(prod.get("screenshot") or ""))
    if shot:
        screenshots.append(shot)

    download_urls: list[str] = []
    soundtrack_urls: list[str] = []
    youtube_id = None
    _append_unique(download_urls, str(prod.get("download") or ""))
    for link in prod.get("downloadLinks") or []:
        if not isinstance(link, dict):
            continue
        href = str(link.get("link") or "").strip()
        if not href:
            continue
        _append_unique(download_urls, href)
        kind = str(link.get("type") or "").strip().lower()
        if "soundtrack" in kind:
            _append_unique(soundtrack_urls, href)
        vid = _youtube_id_from_url(href)
        if vid and youtube_id is None:
            youtube_id = vid
    if youtube_id is None:
        youtube_id = _youtube_id_from_url(str(prod.get("download") or ""))

    csdb = int_or_none(prod.get("csdb"))
    if csdb:
        _append_unique(download_urls, f"https://csdb.dk/release/?id={csdb}")
    zxdemo = int_or_none(prod.get("zxdemo"))
    if zxdemo:
        _append_unique(download_urls, f"https://zxdemo.org/prod.php?id={zxdemo}")

    year = str(prod.get("releaseDate") or "")[:4]
    who = ", ".join(groups)
    vote_avg = _float_or_none(prod.get("voteavg"))
    pouet_rank = int_or_none(prod.get("rank"))
    pouet_cdc = int_or_none(prod.get("cdc"))
    pouet_url = POUET_PROD_PAGE.format(id=pouet_id)
    demozoo_url = DEMOZOO_PROD_PAGE.format(id=demozoo_id) if demozoo_id else None

    metadata = PouetMetadata(
        types=types,
        groups=groups,
        platforms=platforms,
        party=party_lines[0] if party_lines else party or None,
        invitation=invitation,
        credits=credits,
        vote_avg=vote_avg,
        pouet_rank=pouet_rank,
        pouet_cdc=pouet_cdc,
        pouet_popularity=_float_or_none(prod.get("popularity")),
        demozoo_id=demozoo_id,
        pouet_url=pouet_url,
        youtube_video_id=youtube_id,
        soundtrack_urls=soundtrack_urls,
        genres=types,
        companies=groups,
        download_urls=download_urls,
    )
    return PouetRom(
        pouet_id=pouet_id,
        name=str(prod.get("name") or ""),
        summary=build_scene_summary(
            types=types,
            who=who,
            year=year,
            party_lines=party_lines,
            invitation=invitation,
            credits_line=format_credit_line(credits),
            vote_avg=vote_avg,
            pouet_rank=pouet_rank,
            pouet_cdc=pouet_cdc,
            youtube_id=youtube_id,
            demozoo_url=demozoo_url,
            pouet_url=pouet_url,
        ),
        url_cover=screenshots[0] if screenshots else "",
        url_screenshots=screenshots,
        pouet_metadata=metadata,
    )


class PouetHandler(MetadataHandler):
    def __init__(self) -> None:
        self.min_similarity_score: Final = 0.88

    @classmethod
    def is_enabled(cls) -> bool:
        return POUET_API_ENABLED

    async def _request(self, url: str) -> dict:
        await _rate_limiter.acquire()
        headers = {
            "User-Agent": f"RomM/{get_version()}",
            "Accept": "application/json",
        }
        try:
            body = await self._fetch_capped(url, headers=headers)
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning("Can't connect to Pouët API", extra={"exception": str(exc)})
            raise unavailable("Pouët API") from exc
        if body is None:
            return {}
        try:
            data = json.loads(body)
        except ValueError as exc:
            log.error("Error decoding JSON from Pouët: %s", exc)
            return {}
        return data if isinstance(data, dict) else {}

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False
        try:
            data = await self._request(f"{POUET_API_PROD}?id=99")
        except Exception as exc:
            log.error("Error checking Pouët API: %s", exc)
            return False
        return bool(data.get("success"))

    async def get_rom_by_id(self, pouet_id: int) -> PouetRom:
        if not self.is_enabled() or not pouet_id:
            return PouetRom(pouet_id=None)
        data = await self._request(f"{POUET_API_PROD}?id={int(pouet_id)}")
        prod = data.get("prod")
        if not data.get("success") or not isinstance(prod, dict) or not prod.get("id"):
            return PouetRom(pouet_id=None)
        return production_to_rom(prod)

    async def resolve_exact_title(self, title: str) -> int | None:
        """Unique Pouët title → 302 Location ``prod.php?which=<id>``.

        Ambiguous searches return 200 + HTML; we never parse that body.
        """
        query = (title or "").strip()
        if len(query) < 3:
            return None
        await _rate_limiter.acquire()
        httpx_client = ctx_httpx_client.get()
        url = f"{POUET_SEARCH_URL}?{urlencode({'what': query, 'type': 'prod'})}"
        headers = {
            "User-Agent": f"RomM/{get_version()}",
            "Accept": "text/html,application/xhtml+xml",
        }
        # Streamed and never read: an ambiguous title answers 200 with HTML we
        # have no use for, and only the redirect header carries the id.
        try:
            async with httpx_client.stream(
                "GET", url, headers=headers, timeout=25, follow_redirects=False
            ) as res:
                if res.status_code not in {301, 302, 303, 307, 308}:
                    return None
                return pouet_id_from_location(res.headers.get("location") or "")
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning("Pouët title search failed: %s", exc)
            raise unavailable("Pouët API") from exc

    async def get_rom(self, fs_name: str, platform_slug: str) -> PouetRom:
        """Tag first; otherwise unique-title 302. No HTML list parse."""
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return PouetRom(pouet_id=None)
        tagged = extract_pouet_id_from_filename(fs_name)
        if tagged:
            log.debug("Found Pouët ID tag in filename: %s", tagged)
            rom = await self.get_rom_by_id(tagged)
            if rom.get("pouet_id"):
                return rom
            log.warning("Pouët ID %s from filename tag not found", tagged)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        found = await self.resolve_exact_title(search_term)
        if not found:
            log.debug("No unique Pouët title for '%s'", search_term)
            return PouetRom(pouet_id=None)
        log.debug("Pouët exact title '%s' -> %s", search_term, found)
        return await self.get_rom_by_id(found)
