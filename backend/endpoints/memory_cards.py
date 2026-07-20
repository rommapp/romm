from typing import Annotated

from fastapi import Body, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel as PydanticBaseModel

from decorators.auth import protected_route
from endpoints.responses.memory_cards import (
    MemoryCardSchema,
    MemoryCardVersionSchema,
    UserMemoryCardSchema,
)
from handler.auth.constants import Scope
from handler.database import db_memory_card_handler, db_platform_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import build_asset_file_response
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import MemoryCard
from utils.router import APIRouter

router = APIRouter(
    prefix="/memory-cards",
    tags=["memory-cards"],
)


class MemoryCardCreatePayload(PydanticBaseModel):
    name: str
    emulator: str
    # Loose display hint only; never scopes lookup (see MemoryCard model).
    platform_id: int | None = None
    is_public: bool = False


def _card_or_404(card_id: int, user_id: int) -> MemoryCard:
    """Fetch a card the caller may read: their own, or another user's public
    one. Everything else is a 404 (never reveal a private card exists)."""
    card = db_memory_card_handler.get_card_by_id(card_id)
    if not card or (card.user_id != user_id and not card.is_public):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory card with ID {card_id} not found",
        )
    return card


def _owned_card_or_404(card_id: int, user_id: int) -> MemoryCard:
    """Fetch a card the caller owns, for mutations. A card owned by someone
    else is a 404, matching how states scope writes to the owner."""
    card = db_memory_card_handler.get_card(user_id=user_id, id=card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory card with ID {card_id} not found",
        )
    return card


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
def add_memory_card(
    request: Request,
    payload: MemoryCardCreatePayload,
) -> MemoryCardSchema:
    """Create an empty memory card. It hydrates onto a container at the next
    streaming claim; its data accrues as versions on save-and-exit."""
    name = payload.name.strip()
    emulator = payload.emulator.strip()
    if not name or not emulator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both name and emulator are required",
        )

    if payload.platform_id is not None and not db_platform_handler.get_platform(
        payload.platform_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform with ID {payload.platform_id} not found",
        )

    card = db_memory_card_handler.add_card(
        MemoryCard(
            user_id=request.user.id,
            emulator=emulator,
            platform_id=payload.platform_id,
            name=name,
            slot=1,
            is_public=payload.is_public,
        )
    )
    log.info(f"Created memory card {hl(name)} [{emulator}] for {request.user.username}")
    return MemoryCardSchema.model_validate(card)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_memory_cards(
    request: Request, emulator: str | None = None
) -> list[MemoryCardSchema]:
    """The caller's own cards, newest-synced first, optionally one emulator."""
    cards = db_memory_card_handler.get_cards(request.user.id, emulator)
    return [MemoryCardSchema.model_validate(card) for card in cards]


@protected_route(router.get, "/shared", [Scope.ASSETS_READ])
def get_shared_memory_cards(
    request: Request, emulator: str
) -> list[UserMemoryCardSchema]:
    """Cards for an emulator visible to the caller: their own plus other users'
    public ones. Used by the claim picker so a user can hydrate a shared card."""
    cards = db_memory_card_handler.get_shared_cards(
        emulator=emulator, user_id=request.user.id
    )
    return [
        UserMemoryCardSchema.model_validate(
            {
                **MemoryCardSchema.model_validate(card).model_dump(),
                "username": card.user.username,
                "user_avatar_path": card.user.avatar_path,
                "user_updated_at": card.user.updated_at,
            }
        )
        for card in cards
    ]


@protected_route(
    router.get,
    "/versions/{id}/content",
    [Scope.ASSETS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def download_memory_card_version(request: Request, id: int) -> FileResponse:
    """Download a version's card archive. Readable if the caller owns the parent
    card or it is public."""
    version = db_memory_card_handler.get_version_by_id(id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory card version with ID {id} not found",
        )
    # Reuse the card visibility check on the parent.
    _card_or_404(version.memory_card_id, request.user.id)

    try:
        file_path = fs_asset_handler.validate_path(version.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory card file not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory card file not found on disk",
        )

    return build_asset_file_response(file_path, filename=version.file_name)


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_memory_card(request: Request, id: int) -> MemoryCardSchema:
    """A single card: the caller's own or another user's public one."""
    card = _card_or_404(id, request.user.id)
    return MemoryCardSchema.model_validate(card)


@protected_route(router.get, "/{id}/versions", [Scope.ASSETS_READ])
def get_memory_card_versions(
    request: Request, id: int
) -> list[MemoryCardVersionSchema]:
    """A card's snapshot history, newest first."""
    _card_or_404(id, request.user.id)
    versions = db_memory_card_handler.get_versions(id)
    return [MemoryCardVersionSchema.model_validate(v) for v in versions]


@protected_route(
    router.put,
    "/{id}",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def rename_memory_card(
    request: Request,
    id: int,
    name: Annotated[str, Body(embed=True)],
) -> MemoryCardSchema:
    """Rename a card (owner only)."""
    _owned_card_or_404(id, request.user.id)
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name cannot be empty",
        )
    updated = db_memory_card_handler.update_card(id, {"name": cleaned})
    return MemoryCardSchema.model_validate(updated)


@protected_route(
    router.put,
    "/{id}/visibility",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_memory_card_visibility(
    request: Request,
    id: int,
    is_public: Annotated[bool, Body(embed=True)],
) -> MemoryCardSchema:
    """Toggle a card's public/private visibility (owner only). Sharing is
    one-way: a recipient's writes go to their own card, never back to this one."""
    _owned_card_or_404(id, request.user.id)
    updated = db_memory_card_handler.update_card(id, {"is_public": is_public})
    return MemoryCardSchema.model_validate(updated)


@protected_route(
    router.post,
    "/delete",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def delete_memory_cards(
    request: Request,
    cards: Annotated[
        list[int],
        Body(
            description="List of memory card ids to delete.",
            embed=True,
        ),
    ],
) -> list[int]:
    """Delete cards the caller owns, with their version files. Versions cascade
    in the database; their on-disk archives are removed here."""
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No memory cards were provided",
        )

    for card_id in cards:
        card = _owned_card_or_404(card_id, request.user.id)

        # Remove each version's archive before the DB rows cascade away.
        for version in db_memory_card_handler.get_versions(card_id):
            try:
                await fs_asset_handler.remove_file(file_path=version.full_path)
            except FileNotFoundError:
                log.warning(
                    f"Memory card file {hl(version.file_name)} already gone from disk"
                )

        db_memory_card_handler.delete_card(card_id)
        log.info(f"Deleted memory card {hl(card.name)} [{card.emulator}]")

    return cards
