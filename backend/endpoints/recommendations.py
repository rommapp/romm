from typing import Annotated

from fastapi import Query, Request

from decorators.auth import protected_route
from endpoints.responses.recommendation import RecommendedRomSchema
from endpoints.responses.rom import SimpleRomSchema
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.recommendation import FeedBuilder, get_cached_feed, set_cached_feed
from utils.router import APIRouter

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)

DEFAULT_FEED_LIMIT = 20
MAX_FEED_LIMIT = 50

# How much deeper to rank for a user whose visibility rules will drop entries
# from the ranked list. Everyone else ranks exactly as many as they asked for.
VISIBILITY_OVERFETCH = 3


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

    Ranked on demand from the precomputed similarity graph plus the user's
    live play history, so a game played minutes ago already steers the feed.
    """
    user_id = request.user.id
    perms = get_permissions(request)

    # Ranking exactly `limit` and filtering afterwards hands a user with hidden
    # ROMs a short row, or an empty one when the hidden games rank highest.
    hides_anything = not perms.is_admin and bool(
        perms.hidden_rom_ids or perms.hidden_platform_ids
    )
    ranked_limit = limit * VISIBILITY_OVERFETCH if hides_anything else limit

    feed = None if refresh else get_cached_feed(user_id, ranked_limit)
    if feed is None:
        feed = FeedBuilder(user_id).build(limit=ranked_limit)
        set_cached_feed(user_id, ranked_limit, feed)

    visible = [
        RecommendedRomSchema(
            rom=SimpleRomSchema.from_orm_with_request(item.rom, request),
            score=item.score,
            reasons=item.reasons,  # type: ignore[arg-type]
            seed_rom_id=item.seed_rom_id,
            seed_rom_name=item.seed_rom_name,
        )
        for item in feed
        if perms.can_see_rom(item.rom.id, item.rom.platform_id)
    ]

    return visible[:limit]
