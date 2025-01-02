from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from config import SCREENSCRAPER_API_KEY, SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client

from .base_hander import MetadataHandler

# Used to display the Screenscraper API status in the frontend
SS_API_ENABLED: Final = bool(SCREENSCRAPER_USER) and bool(SCREENSCRAPER_PASSWORD)


class IGDBPlatform(TypedDict):
    slug: str
    igdb_id: int | None
    name: NotRequired[str]


class IGDBAgeRating(TypedDict):
    rating: str
    category: str
    rating_cover_url: str


class IGDBMetadataPlatform(TypedDict):
    igdb_id: int
    name: str


class IGDBRelatedGame(TypedDict):
    id: int
    name: str
    slug: str
    type: str
    cover_url: str


class IGDBMetadata(TypedDict):
    total_rating: str
    aggregated_rating: str
    first_release_date: int | None
    youtube_video_id: str | None
    genres: list[str]
    franchises: list[str]
    alternative_names: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[IGDBAgeRating]
    platforms: list[IGDBMetadataPlatform]
    expansions: list[IGDBRelatedGame]
    dlcs: list[IGDBRelatedGame]
    remasters: list[IGDBRelatedGame]
    remakes: list[IGDBRelatedGame]
    expanded_games: list[IGDBRelatedGame]
    ports: list[IGDBRelatedGame]
    similar_games: list[IGDBRelatedGame]


class IGDBRom(TypedDict):
    igdb_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    igdb_metadata: NotRequired[IGDBMetadata]


def extract_metadata_from_igdb_rom(
    rom: dict, video_id: str | None = None
) -> IGDBMetadata:
    return IGDBMetadata(
        {
            "youtube_video_id": video_id,
            "total_rating": str(round(rom.get("total_rating", 0.0), 2)),
            "aggregated_rating": str(round(rom.get("aggregated_rating", 0.0), 2)),
            "first_release_date": rom.get("first_release_date", None),
            "genres": pydash.map_(rom.get("genres", []), "name"),
            "franchises": pydash.compact(
                [rom.get("franchise.name", None)]
                + pydash.map_(rom.get("franchises", []), "name")
            ),
            "alternative_names": pydash.map_(rom.get("alternative_names", []), "name"),
            "collections": pydash.map_(rom.get("collections", []), "name"),
            "game_modes": pydash.map_(rom.get("game_modes", []), "name"),
            "companies": pydash.map_(rom.get("involved_companies", []), "company.name"),
            "platforms": [
                IGDBMetadataPlatform(igdb_id=p.get("id", ""), name=p.get("name", ""))
                for p in rom.get("platforms", [])
            ],
            "age_ratings": [],
            "expansions": [
                IGDBRelatedGame(
                    id=e["id"],
                    slug=e["slug"],
                    name=e["name"],
                    cover_url=pydash.get(e, "cover.url", ""),
                    type="expansion",
                )
                for e in rom.get("expansions", [])
            ],
            "dlcs": [
                IGDBRelatedGame(
                    id=d["id"],
                    slug=d["slug"],
                    name=d["name"],
                    cover_url=pydash.get(d, "cover.url", ""),
                    type="dlc",
                )
                for d in rom.get("dlcs", [])
            ],
            "remasters": [
                IGDBRelatedGame(
                    id=r["id"],
                    slug=r["slug"],
                    name=r["name"],
                    cover_url=pydash.get(r, "cover.url", ""),
                    type="remaster",
                )
                for r in rom.get("remasters", [])
            ],
            "remakes": [
                IGDBRelatedGame(
                    id=r["id"],
                    slug=r["slug"],
                    name=r["name"],
                    cover_url=pydash.get(r, "cover.url", ""),
                    type="remake",
                )
                for r in rom.get("remakes", [])
            ],
            "expanded_games": [
                IGDBRelatedGame(
                    id=g["id"],
                    slug=g["slug"],
                    name=g["name"],
                    cover_url=pydash.get(g, "cover.url", ""),
                    type="expanded",
                )
                for g in rom.get("expanded_games", [])
            ],
            "ports": [
                IGDBRelatedGame(
                    id=p["id"],
                    slug=p["slug"],
                    name=p["name"],
                    cover_url=pydash.get(p, "cover.url", ""),
                    type="port",
                )
                for p in rom.get("ports", [])
            ],
            "similar_games": [
                IGDBRelatedGame(
                    id=s["id"],
                    slug=s["slug"],
                    name=s["name"],
                    cover_url=pydash.get(s, "cover.url", ""),
                    type="similar",
                )
                for s in rom.get("similar_games", [])
            ],
        }
    )


class SSBaseHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.screenscraper.fr/api2"
        self.search_endpoint = f"{self.BASE_URL}/jeuRecherche.php"
        self.auth_params = {
            "ssid": SCREENSCRAPER_USER,
            "sspassword": SCREENSCRAPER_PASSWORD,
            "devid": SCREENSCRAPER_USER,
            "devpassword": SCREENSCRAPER_API_KEY,
            "softname": "romm",
        }
        self.output_param = {"output": "json"}
        self.LOGIN_ERROR_CHECK: Final = "Erreur de login"

    async def _request(
        self, url: str, search_term: str, platform_id: int, timeout: int = 120
    ) -> list:
        httpx_client = ctx_httpx_client.get()
        try:
            masked_params = self._mask_sensitive_values(self.auth_params)
            log.debug(
                "API request: URL=%s, Params=%s, Timeout=%s",
                url,
                masked_params,
                timeout,
            )
            res = await httpx_client.get(
                url,
                params={
                    **self.auth_params,
                    **self.output_param,
                    "recherche": search_term,
                    "systemeid": platform_id,
                },
                headers={},
                timeout=timeout,
            )

            res.raise_for_status()
            if self.LOGIN_ERROR_CHECK in res.text:
                log.error("Invalid screenscraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid screenscraper credentials",
                )
            matches: list[dict] = []
            for rom in res.json().get("response", []).get("jeux", []):
                noms = rom.get("noms", [])
                if len(noms) > 0:
                    name = ""
                    for n in noms:
                        region = n.get("region", "")
                        text = n.get("text", "")
                        if region and text:
                            if region == "ss":
                                name = text
                                break
                    if not name:
                        continue
                synopses = rom.get("synopsis", [])
                if len(synopses) > 0:
                    summary = ""
                    for s in synopses:
                        langue = s.get("langue", "")
                        text = s.get("text", "")
                        if langue and text:
                            if langue == "en":
                                summary = text
                                break
                url_covers = rom.get("medias", [])
                if len(url_covers) > 0:
                    url_cover = ""
                    for u in url_covers:
                        if (
                            u.get("region", "") == "us"
                            and u.get("type", "") == "box-2D"
                            and u.get("parent", "") == "jeu"
                        ):
                            url_cover = u.get("url", "")
                            break
                matches.append(
                    {
                        "ss_id": rom.get("id", ""),
                        "name": name,
                        "slug": name,
                        "summary": summary,
                        "url_cover": url_cover,
                        "ss_metadata": {},
                    }
                )
            return matches
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to IGDB", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection",
            ) from exc

    async def search_rom(self, search_term, platform) -> list[dict]:
        matches = await self._request(
            self.search_endpoint,
            search_term,
            SLUG_TO_SS_ID.get(platform.slug, {"id": 1}).get("id", 1),
        )
        return matches


class SlugToSSId(TypedDict):
    id: int
    name: str


SLUG_TO_SS_ID: dict[str, SlugToSSId] = {
    "gba": {"id": 12, "name": "Game Boy Advance"},
}

# Reverse lookup
SS_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_SS_ID.items()}
