"""Demozoo metadata for demoscene productions.

Match by production id (filename tag ``(demozoo-N)`` or Edit-ROM id / URL), or by
title search via ``?title=`` (never ``?search=``) ranked with Jaro-Winkler.

Public JSON API, no key.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, NotRequired, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from config import DEMOZOO_API_ENABLED
from logger.logger import log
from utils import get_version, int_or_none, valid_youtube_id
from utils.platform_slugs import UniversalPlatformSlug as UPS
from utils.rate_limiter import RateLimiter

from .base_handler import BaseRom, MetadataHandler, unavailable

DEMOZOO_TAG_REGEX = re.compile(r"\(demozoo-(\d+)\)", re.IGNORECASE)
DEMOZOO_PROD_ID_RE = re.compile(
    r"(?:demozoo\.org)/(?:api/v1/)?productions/(\d+)", re.IGNORECASE
)
DEMOZOO_API_ROOT: Final[str] = "https://demozoo.org/api/v1"
DEMOZOO_PROD_PAGE: Final[str] = "https://demozoo.org/productions/{id}/"
POUET_PROD_PAGE: Final[str] = "https://www.pouet.net/prod.php?which={id}"
YOUTUBE_WATCH: Final[str] = "https://www.youtube.com/watch?v={id}"
# Overview notes stay one clause; Demozoo editorial text is rare and long.
_NOTES_MAX_LEN: Final[int] = 80
# Demozoo asks for a polite UA; stay well under burst.
_rate_limiter = RateLimiter(2.0)


class DemozooCredit(TypedDict, total=False):
    name: str
    role: str


class DemozooMetadata(TypedDict, total=False):
    types: list[str]
    groups: list[str]
    platforms: list[str]
    party: str | None
    party_id: int | None
    party_line: str | None
    invitation: str | None
    credits: list[DemozooCredit]
    tags: list[str]
    demozoo_url: str | None
    pouet_id: int | None
    pouet_url: str | None
    csdb_id: int | None
    csdb_url: str | None
    youtube_video_id: str | None
    first_release_date: int | None
    companies: list[str]
    genres: list[str]
    collections: list[str]
    download_urls: list[str]


class DemozooRom(BaseRom):
    demozoo_id: int | None
    demozoo_metadata: NotRequired[DemozooMetadata]


def extract_demozoo_id_from_filename(fs_name: str) -> int | None:
    """Extract Demozoo ID from a filename tag like ``(demozoo-108)``."""
    match = DEMOZOO_TAG_REGEX.search(fs_name)
    if match:
        return int_or_none(match.group(1))
    return None


def demozoo_id_from_url(value: str) -> int | None:
    """Parse a production id from a Demozoo page / API URL, or a bare number."""
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int_or_none(text)
    match = DEMOZOO_PROD_ID_RE.search(text)
    return int_or_none(match.group(1)) if match else None


def _youtube_id_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    if host in {"youtu.be", "m.youtu.be"}:
        return valid_youtube_id(parsed.path.lstrip("/").split("/", 1)[0])
    if host not in {
        "youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
    }:
        return None
    qs = parse_qs(parsed.query)
    if qs.get("v"):
        return valid_youtube_id(qs["v"][0])
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"embed", "shorts", "v", "live", "e"}:
        return valid_youtube_id(parts[1])
    return None


def _pouet_id_from_url(url: str) -> int | None:
    if "which=" not in url:
        return None
    tail = url.split("which=", 1)[1]
    digits = ""
    for ch in tail:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int_or_none(digits) if digits else None


def http_url(value: Any) -> str | None:
    """Keep http(s) links only. Metadata tab renders these as hrefs."""
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text
    return None


def _append_unique(bucket: list[str], value: str | None) -> None:
    text = http_url(value)
    if text and text not in bucket:
        bucket.append(text)


def format_credit_line(
    credits: Sequence[Mapping[str, object]], *, limit: int = 8
) -> str:
    """'Graphics: Marvel, Pixel · Music: Purple Motion' — cap names."""
    by_role: dict[str, list[str]] = {}
    order: list[str] = []
    for row in credits:
        name = str(row.get("name") or "").strip()
        role = str(row.get("role") or "Credits").strip() or "Credits"
        if not name:
            continue
        if role not in by_role:
            by_role[role] = []
            order.append(role)
        if name not in by_role[role]:
            by_role[role].append(name)
    bits: list[str] = []
    taken = 0
    for role in order:
        names: list[str] = []
        for name in by_role[role]:
            if taken >= limit:
                break
            names.append(name)
            taken += 1
        if names:
            bits.append(f"{role}: {', '.join(names)}")
        if taken >= limit:
            break
    return " · ".join(bits)


def format_pouet_score(
    vote_avg: float | None,
    rank: int | None = None,
    cdc: int | None = None,
) -> str:
    if vote_avg is None and rank is None and not cdc:
        return ""
    bits: list[str] = []
    if vote_avg is not None:
        bits.append(f"Pouët {vote_avg:.3f}")
    # Site-wide rank past the first couple of thousand is noise on new prods.
    if rank is not None and rank <= 2000:
        bits.append(f"#{rank}")
    if cdc:
        bits.append(f"CdC {cdc}")
    return " · ".join(bits)


# Demozoo tags we surface on Overview. Most tags are catalog noise
# (charset-*, trainer, screenshots-needed). Only play-relevant flags.
_OVERVIEW_TAG_NOTES: dict[str, str] = {
    "no-sound": "no sound",
    "hidden-part": "hidden part",
}


def scene_notes_from_tags(tags: list[str] | None) -> list[str]:
    """Map Demozoo tags to short Overview notes. Unknown tags are ignored."""
    notes: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        key = str(raw).strip().lower()
        label = _OVERVIEW_TAG_NOTES.get(key)
        if label and label not in seen:
            seen.add(label)
            notes.append(label)
    return notes


def _clip_overview_note(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _NOTES_MAX_LEN:
        return cleaned
    return cleaned[: _NOTES_MAX_LEN - 1].rstrip() + "…"


def scene_notes_from_production(
    data: dict[str, Any], tags: list[str] | None = None
) -> list[str]:
    """Tags plus optional JSON ``notes`` / ``hidden_parts``. Skip empty."""
    notes = scene_notes_from_tags(tags)
    raw_notes = data.get("notes")
    if isinstance(raw_notes, str):
        clipped = _clip_overview_note(raw_notes)
        if clipped and clipped not in notes:
            notes.append(clipped)
    hidden = data.get("hidden_parts")
    if hidden and "hidden part" not in notes:
        notes.append("hidden part")
    return notes


def build_scene_summary(
    *,
    types: list[str],
    who: str,
    year: str,
    party_lines: list[str],
    invitation: str | None = None,
    credits_line: str | None = None,
    notes: list[str] | None = None,
    vote_avg: float | None = None,
    pouet_rank: int | None = None,
    pouet_cdc: int | None = None,
    youtube_id: str | None = None,
    demozoo_url: str | None = None,
    pouet_url: str | None = None,
    csdb_url: str | None = None,
) -> str:
    """Overview line. Demozoo has no prose; v2 also has no YouTube player."""
    bits: list[str] = []
    kind = ", ".join(t for t in types if t) or "Production"
    head = kind
    if who:
        head += f" by {who}"
    if year:
        head += f" ({year})"
    bits.append(head)
    for line in party_lines:
        if line and line not in bits:
            bits.append(line)
    if invitation and invitation not in bits:
        bits.append(invitation)
    if credits_line and credits_line not in bits:
        bits.append(credits_line)
    for note in notes or []:
        if note and note not in bits:
            bits.append(note)
    score = format_pouet_score(vote_avg, pouet_rank, pouet_cdc)
    if score:
        bits.append(score)
    if youtube_id:
        bits.append(YOUTUBE_WATCH.format(id=youtube_id))
    if demozoo_url:
        bits.append(demozoo_url)
    if pouet_url:
        bits.append(pouet_url)
    if csdb_url:
        bits.append(csdb_url)
    return " · ".join(bits)


def splice_csdb_url(summary: str, csdb_url: str | None) -> str:
    """Append the CSDb release page if it is not already on the Overview line."""
    url = (csdb_url or "").strip()
    if not url or not summary or url in summary:
        return summary
    return f"{summary} · {url}"


def splice_pouet_vote(
    summary: str,
    vote_avg: float | None,
    rank: int | None = None,
    cdc: int | None = None,
) -> str:
    """Keep Demozoo party/credits/URLs; insert Pouët score before the links."""
    token = format_pouet_score(vote_avg, rank, cdc)
    if not token or not summary:
        return summary
    parts = [part for part in summary.split(" · ") if part]
    parts = [part for part in parts if not part.startswith("Pouët ")]
    # Drop a leftover lone "#14" / "CdC N" from a previous splice.
    parts = [
        part
        for part in parts
        if not (part.startswith("#") and part[1:].isdigit())
        and not part.startswith("CdC ")
    ]
    idx = next(
        (i for i, part in enumerate(parts) if part.startswith("http")), len(parts)
    )
    parts.insert(idx, token)
    return " · ".join(parts)


def _unix_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(value[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(dt.timestamp())


def production_to_rom(data: dict[str, Any]) -> DemozooRom:
    platforms = [
        p.get("name") or "" for p in data.get("platforms") or [] if isinstance(p, dict)
    ]
    types = [
        t.get("name") or "" for t in data.get("types") or [] if isinstance(t, dict)
    ]
    groups: list[str] = []
    authors: list[str] = []
    for nick in data.get("author_nicks") or []:
        if not isinstance(nick, dict):
            continue
        name = nick.get("name") or (nick.get("releaser") or {}).get("name") or ""
        if not name:
            continue
        if (nick.get("releaser") or {}).get("is_group"):
            groups.append(name)
        else:
            authors.append(name)

    party = None
    party_id = None
    party_lines: list[str] = []
    for row in data.get("competition_placings") or []:
        if not isinstance(row, dict):
            continue
        comp = row.get("competition") or {}
        if not isinstance(comp, dict):
            comp = {}
        party_obj = comp.get("party") if isinstance(comp.get("party"), dict) else {}
        party_name = str((party_obj or {}).get("name") or "")
        raw_party_id = (party_obj or {}).get("id")
        if party_name and party is None:
            party = party_name
        if party_id is None and raw_party_id is not None:
            try:
                party_id = int(raw_party_id)
            except (TypeError, ValueError):
                party_id = None
        line = party_name
        comp_name = str(comp.get("name") or "")
        if comp_name:
            line = f"{line} / {comp_name}" if line else comp_name
        ranking = str(row.get("ranking") or row.get("position") or "")
        if ranking:
            line = f"{line} #{ranking}" if line else f"#{ranking}"
        if line and line not in party_lines:
            party_lines.append(line)
        if len(party_lines) >= 3:
            break

    credits: list[DemozooCredit] = []
    for row in data.get("credits") or []:
        if not isinstance(row, dict):
            continue
        nick = row.get("nick") or {}
        if not isinstance(nick, dict):
            nick = {}
        name = nick.get("name") or (nick.get("releaser") or {}).get("name") or ""
        role = str(row.get("category") or row.get("role") or "").strip()
        if name:
            credits.append(DemozooCredit(name=str(name), role=role))

    tags = [str(tag) for tag in (data.get("tags") or []) if tag]

    invitation = None
    for party_row in data.get("invitation_parties") or []:
        if isinstance(party_row, dict) and party_row.get("name"):
            invitation = f"Invitation for {party_row['name']}"
            break

    pouet_id = None
    csdb_id = None
    youtube_id = None
    download_urls: list[str] = []
    for link in data.get("external_links") or []:
        if not isinstance(link, dict):
            continue
        cls = link.get("link_class") or ""
        url = str(link.get("url") or "").strip()
        if not url:
            continue
        if cls == "PouetProduction" and pouet_id is None:
            pouet_id = _pouet_id_from_url(url)
        if cls == "CsdbRelease" and csdb_id is None:
            from handler.metadata.csdb_handler import csdb_id_from_url

            csdb_id = csdb_id_from_url(url)
        vid = _youtube_id_from_url(url)
        if vid and youtube_id is None:
            youtube_id = vid
        if cls not in {"PouetProduction", "CsdbRelease"}:
            _append_unique(download_urls, url)

    screenshots: list[str] = []
    for shot in data.get("screenshots") or []:
        if not isinstance(shot, dict):
            continue
        shot_url = http_url(shot.get("standard_url") or shot.get("original_url"))
        if shot_url:
            screenshots.append(shot_url)

    for link in data.get("download_links") or []:
        if not isinstance(link, dict):
            continue
        _append_unique(download_urls, str(link.get("url") or ""))

    demozoo_id = int(data["id"])
    title = str(data.get("title") or "")
    release = data.get("release_date")
    year = (release or "")[:4]
    who = ", ".join(groups or authors)
    demozoo_url = http_url(data.get("demozoo_url")) or DEMOZOO_PROD_PAGE.format(
        id=demozoo_id
    )
    pouet_url = POUET_PROD_PAGE.format(id=pouet_id) if pouet_id else None
    csdb_url = f"https://csdb.dk/release/?id={csdb_id}" if csdb_id else None
    clean_types = [t for t in types if t]
    companies = groups or authors
    credit_line = format_credit_line(credits)
    overview_notes = scene_notes_from_production(data, tags)
    metadata = DemozooMetadata(
        types=clean_types,
        groups=groups,
        platforms=[p for p in platforms if p],
        party=party,
        party_id=party_id,
        party_line=party_lines[0] if party_lines else None,
        invitation=invitation,
        credits=credits,
        tags=tags,
        demozoo_url=demozoo_url,
        pouet_id=pouet_id,
        pouet_url=pouet_url,
        csdb_id=csdb_id,
        csdb_url=csdb_url,
        youtube_video_id=youtube_id,
        first_release_date=_unix_date(release),
        companies=companies,
        genres=clean_types,
        collections=tags,
        download_urls=download_urls,
    )
    return DemozooRom(
        demozoo_id=demozoo_id,
        name=title,
        summary=build_scene_summary(
            types=clean_types,
            who=who,
            year=year,
            party_lines=party_lines,
            invitation=invitation,
            credits_line=credit_line,
            notes=overview_notes,
            youtube_id=youtube_id,
            demozoo_url=demozoo_url,
            pouet_url=pouet_url,
            csdb_url=csdb_url,
        ),
        url_cover=screenshots[0] if screenshots else "",
        url_screenshots=screenshots,
        demozoo_metadata=metadata,
    )


class DemozooHandler(MetadataHandler):
    def __init__(self) -> None:
        self.min_similarity_score: Final = 0.88

    @classmethod
    def is_enabled(cls) -> bool:
        return DEMOZOO_API_ENABLED

    async def _request(self, url: str) -> dict:
        await _rate_limiter.acquire()
        headers = {
            "User-Agent": f"RomM/{get_version()}",
            "Accept": "application/json",
        }
        try:
            body = await self._fetch_capped(url, headers=headers)
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning("Can't connect to Demozoo API", extra={"exception": str(exc)})
            raise unavailable("Demozoo API") from exc
        if body is None:
            return {}
        try:
            data = json.loads(body)
        except ValueError as exc:
            log.error("Error decoding JSON from Demozoo: %s", exc)
            return {}
        return data if isinstance(data, dict) else {}

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False
        try:
            data = await self._request(
                f"{DEMOZOO_API_ROOT}/productions/?title=Second%20Reality"
            )
        except Exception as exc:
            log.error("Error checking Demozoo API: %s", exc)
            return False
        return bool(data.get("results"))

    async def get_rom_by_id(self, demozoo_id: int) -> DemozooRom:
        if not self.is_enabled() or not demozoo_id:
            return DemozooRom(demozoo_id=None)
        data = await self._request(f"{DEMOZOO_API_ROOT}/productions/{int(demozoo_id)}/")
        if not data.get("id"):
            return DemozooRom(demozoo_id=None)
        return production_to_rom(data)

    def get_platform(self, slug: str) -> dict:
        if slug not in DEMOZOO_PLATFORM_LIST:
            return {"slug": slug, "demozoo_id": None, "name": slug}
        platform = DEMOZOO_PLATFORM_LIST[UPS(slug)]
        return {
            "slug": slug,
            "demozoo_id": platform["id"],
            "name": platform["name"],
        }

    async def search_productions(
        self, title: str, platform_id: int | None = None, *, limit: int = 20
    ) -> list[dict]:
        """Demozoo title filter. Do not use ``?search=``."""
        params: dict[str, str] = {"title": title}
        if platform_id is not None:
            params["platform"] = str(platform_id)
        data = await self._request(
            f"{DEMOZOO_API_ROOT}/productions/?{urlencode(params)}"
        )
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []
        return [
            row for row in results[:limit] if isinstance(row, dict) and row.get("id")
        ]

    async def get_rom(self, fs_name: str, platform_slug: str) -> DemozooRom:
        """Filename tag first; otherwise title search and rank."""
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return DemozooRom(demozoo_id=None)

        tagged = extract_demozoo_id_from_filename(fs_name)
        if tagged:
            log.debug("Found Demozoo ID tag in filename: %s", tagged)
            rom = await self.get_rom_by_id(tagged)
            if rom.get("demozoo_id"):
                return rom
            log.warning("Demozoo ID %s from filename tag not found", tagged)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        if not search_term:
            return DemozooRom(demozoo_id=None)

        platform = self.get_platform(platform_slug)
        hits = await self.search_productions(search_term, platform.get("demozoo_id"))
        if not hits:
            log.debug("Could not find '%s' on Demozoo", search_term)
            return DemozooRom(demozoo_id=None)

        names = [str(h.get("title") or "") for h in hits]
        best_match, best_score = self.find_best_match(
            search_term, names, min_similarity_score=self.min_similarity_score
        )
        if not best_match:
            log.debug("No good Demozoo match for '%s'", search_term)
            return DemozooRom(demozoo_id=None)

        best = next((h for h in hits if h.get("title") == best_match), None)
        if not best:
            return DemozooRom(demozoo_id=None)

        log.debug(
            "Found Demozoo match for '%s' -> '%s' (score: %.3f)",
            search_term,
            best_match,
            best_score,
        )
        # List payload is thin; refetch so covers / links are complete.
        return await self.get_rom_by_id(int(best["id"]))

    async def get_matched_roms_by_name(
        self, search_term: str, platform_slug: str
    ) -> list[DemozooRom]:
        """Picker list for Identify / search-by-name."""
        if not self.is_enabled() or not search_term:
            return []
        platform = self.get_platform(platform_slug)
        hits = await self.search_productions(
            search_term, platform.get("demozoo_id"), limit=15
        )
        out: list[DemozooRom] = []
        for hit in hits:
            try:
                out.append(production_to_rom(hit))
            except (KeyError, TypeError, ValueError):
                continue
        return out


class _DemozooPlatform(TypedDict):
    id: int
    name: str


DEMOZOO_PLATFORM_LIST: dict[UPS, _DemozooPlatform] = {
    UPS.WIN: {"id": 1, "name": "Windows"},
    UPS.DOS: {"id": 4, "name": "MS-Dos"},
    UPS.AMIGA: {"id": 5, "name": "Amiga OCS/ECS"},
    UPS.C64: {"id": 3, "name": "Commodore 64"},
    UPS.NES: {"id": 25, "name": "Nintendo Entertainment System (NES)"},
    UPS.SNES: {"id": 34, "name": "Nintendo SNES/Super FamiCom"},
    UPS.GENESIS: {"id": 22, "name": "Sega Megadrive/Genesis"},
}
