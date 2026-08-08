from __future__ import annotations

from pydantic import BaseModel

from endpoints.responses.rom import SimpleRomSchema


class SimilarityReasonSchema(BaseModel):
    """Why two games were linked, e.g. {"facet": "franchise", "value": "Metroid"}.

    `facet` is one of the metadata facets the engine scores on (genre,
    franchise, collection, company, game_mode, decade), or "igdb" when the
    link came from IGDB's own related-games list, or "top_rated" for the
    cold-start feed. The frontend maps it to a translated label.
    """

    facet: str
    value: str


class SimilarRomSchema(BaseModel):
    rom: SimpleRomSchema
    score: float
    reasons: list[SimilarityReasonSchema]


class RecommendedRomSchema(SimilarRomSchema):
    # The played game that pulled this recommendation in, for "Because you
    # played X". Absent on cold-start results, which have no seed.
    seed_rom_id: int | None = None
    seed_rom_name: str | None = None
