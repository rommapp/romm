import asyncio
import re
from pathlib import Path
from typing import Annotated

from fastapi import Body, File, HTTPException, Request, UploadFile, status
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
from models.assets import MemoryCard, MemoryCardVersion
from utils.memory_cards import (
    MEMORY_CARD_MAX_BYTES,
    UnsafeCardArchive,
    assert_card_archive_safe,
    store_memory_card_version,
)
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size

router = APIRouter(
    prefix="/memory-cards",
    tags=["memory-cards"],
)

MEMORY_CARD_FILE_UPLOAD = File(..., description="Memory card archive to upload.")

# The emulator name is a folder under the user's memory_cards directory, so it
# is held to what a folder may be called rather than to any list of emulators.
EMULATOR_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")


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

    if not EMULATOR_NAME_RE.match(emulator):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not a valid emulator name: {emulator}",
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
    public ones. Browsing and download only: mounting a card at claim is
    owner-scoped, so the picker lists the caller's own cards instead."""
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


# The expansion check decompresses what the uploader sent, so it runs off the
# loop. The executor it lands in is the one every other blocking call in the
# process shares, hence the cap on how many uploads may occupy it at once.
_ARCHIVE_CHECKS = asyncio.Semaphore(2)


async def _assert_safe_archive(content: bytes) -> None:
    """The shared archive check, as a 400. Covers the whole gate: readable zip,
    no escaping paths, no symlinks, no runaway expansion.
    """
    try:
        async with _ARCHIVE_CHECKS:
            await asyncio.to_thread(assert_card_archive_safe, content)
    except UnsafeCardArchive as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Memory card archive rejected, {exc}",
        ) from None


def _version_file_or_404(version: MemoryCardVersion) -> Path:
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
    return file_path


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

    return build_asset_file_response(
        _version_file_or_404(version), filename=version.file_name
    )


@protected_route(
    router.get,
    "/{id}/content",
    [Scope.ASSETS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def download_memory_card(request: Request, id: int) -> FileResponse:
    """Download the card as it stands now, without going through its history.

    This is the newest version, which is also what the next claim hydrates onto
    a container, so what comes down here is what the emulator would boot with.
    A card that has never been synced has nothing to serve and 404s."""
    _card_or_404(id, request.user.id)

    version = db_memory_card_handler.get_latest_version(id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory card has no stored data yet",
        )

    return build_asset_file_response(
        _version_file_or_404(version), filename=version.file_name
    )


@protected_route(
    router.post,
    "/{id}/versions",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_413_CONTENT_TOO_LARGE: {},
    },
)
async def upload_memory_card_version(
    request: Request,
    id: int,
    cardFile: UploadFile = MEMORY_CARD_FILE_UPLOAD,
) -> MemoryCardVersionSchema:
    """Store a card image the user supplied as the card's newest version, which
    is what the next claim hydrates onto the container (owner only).

    Only the zip layout the broker exchanges is accepted. A bare card image
    (`.ps2`, `.raw`) is refused rather than stored, because nothing downstream
    would notice until hydrate pushed it and the emulator rejected the card.
    """
    check_asset_upload_size(cardFile, "Memory card file")
    card = _owned_card_or_404(id, request.user.id)

    content = await cardFile.read(MEMORY_CARD_MAX_BYTES + 1)
    if len(content) > MEMORY_CARD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Memory card exceeds the maximum size of "
                f"{MEMORY_CARD_MAX_BYTES} bytes"
            ),
        )
    await _assert_safe_archive(content)

    # The version this call wrote, not the card's latest: a teardown evacuating
    # the same card alongside the upload would make the latest describe a
    # snapshot the uploader never sent.
    version = await store_memory_card_version(
        request.user, card, content, deduplicate=False
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory card upload was not stored",
        )

    log.info(f"Uploaded memory card {hl(card.name)} [{card.emulator}]")
    return MemoryCardVersionSchema.model_validate(version)


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_memory_card(request: Request, id: int) -> MemoryCardSchema:
    """A single card: the caller's own or another user's public one."""
    card = _card_or_404(id, request.user.id)
    return MemoryCardSchema.model_validate(card)


def _reconcile_missing(version: MemoryCardVersion) -> bool:
    """Whether this version's archive is gone, persisting the answer.

    Nothing else writes `missing_from_fs`, and the history is the only place a
    user can see that a snapshot is unrecoverable before clicking download, so
    the listing is where the flag is brought back in line with the disk.
    """
    try:
        path = fs_asset_handler.validate_path(version.full_path)
        missing = not path.is_file()
    except (ValueError, OSError):
        missing = True

    if missing != version.missing_from_fs:
        db_memory_card_handler.set_version_missing(version.id, missing)
    return missing


@protected_route(router.get, "/{id}/versions", [Scope.ASSETS_READ])
def get_memory_card_versions(
    request: Request, id: int
) -> list[MemoryCardVersionSchema]:
    """A card's snapshot history, newest first."""
    _card_or_404(id, request.user.id)
    versions = db_memory_card_handler.get_versions(id)
    return [
        MemoryCardVersionSchema.model_validate(v).model_copy(
            update={"missing_from_fs": _reconcile_missing(v)}
        )
        for v in versions
    ]


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
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory card not found"
        )
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
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory card not found"
        )
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

    # Resolve every card up front: deletion is irreversible and spans one
    # transaction per card, so a bad id in the batch must fail before the
    # first archive is removed rather than half way through.
    owned = [
        (card_id, _owned_card_or_404(card_id, request.user.id)) for card_id in cards
    ]

    for card_id, card in owned:
        # The delete reports the archives that went with it, so the removal list
        # cannot miss a version written while the batch was running. A file that
        # will not budge (permissions, a locked mount) must not abort the batch:
        # the rest of the cards would be left untouched with nothing to tell the
        # caller how far it got. An orphaned archive is recoverable, a
        # half-deleted batch is not.
        for path in db_memory_card_handler.delete_card(card_id):
            try:
                await fs_asset_handler.remove_file(file_path=path)
            except FileNotFoundError:
                log.warning(f"Memory card file {hl(path)} already gone from disk")
            except OSError as exc:
                log.error(
                    f"Could not remove memory card file {hl(path)}, "
                    f"leaving it orphaned: {exc}"
                )

        log.info(f"Deleted memory card {hl(card.name)} [{card.emulator}]")

    return cards
