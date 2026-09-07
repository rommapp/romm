from typing import Annotated

from fastapi import Query, Request

from decorators.auth import protected_route
from endpoints.responses.recommendation import RecommendedRomSchema
from endpoints.responses.rom import SimpleRomSchema
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.recommendation import recommended_roms
from utils.router import APIRouter

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)

DEFAULT_FEED_LIMIT = 20
MAX_FEED_LIMIT = 50


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_recommendations(
    request: Request,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_FEED_LIMIT, description="Maximum recommendations to return"),
    ] = DEFAULT_FEED_LIMIT,
    refresh: Annotated[
        bool, Query(description="Bypass the cached feed and rank again")
    ] = False,
) -> list[RecommendedRomSchema]:
    """Personalised game recommendations for the current user.

    Ranked on demand from the similarity graph plus live play history, so a
    game played minutes ago already steers the feed.
    """
    feed = recommended_roms(
        request.user.id,
        limit=limit,
        permissions=get_permissions(request),
        refresh=refresh,
    )

    return [
        RecommendedRomSchema(
            rom=SimpleRomSchema.from_orm_with_request(item.rom, request),
            score=item.score,
            reasons=item.reasons,  # type: ignore[arg-type]
            seed_rom_id=item.seed_rom_id,
            seed_rom_name=item.seed_rom_name,
        )
        for item in feed
    ]
