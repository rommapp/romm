from __future__ import annotations

from pydantic import BaseModel

from endpoints.responses.rom import SimpleRomSchema
from handler.recommendation.scoring import Facet


class SimilarityReasonSchema(BaseModel):
    """Why two games were linked, e.g. {"facet": "franchise", "value": "Metroid"}.

    `value` is empty for facets with no value of their own, which the frontend
    renders as a translated phrase instead.
    """

    facet: Facet
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
