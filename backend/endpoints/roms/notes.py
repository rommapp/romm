from typing import Annotated

from fastapi import Body, HTTPException
from fastapi import Path as PathVar
from fastapi import Query, Request, status

from decorators.auth import protected_route
from endpoints.responses.rom import UserNoteSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from models.rom import RomNote
from utils.router import APIRouter

router = APIRouter()

DEFAULT_PUBLIC_ONLY = Query(False, description="Only return public notes")
DEFAULT_SEARCH = Query(None, description="Search notes by title or content")
DEFAULT_TAGS = Query(None, description="Filter by tags")


@protected_route(
    router.get,
    "/{id}/notes",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_notes(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    public_only: bool = DEFAULT_PUBLIC_ONLY,
    search: str = DEFAULT_SEARCH,
    tags: list[str] = DEFAULT_TAGS,
) -> list[UserNoteSchema]:
    """Get all notes for a ROM."""
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if tags is None:
        tags = []

    notes = db_rom_handler.get_rom_notes(
        rom_id=id,
        user_id=request.user.id,
        public_only=public_only,
        search=search,
        tags=tags,
    )

    return [UserNoteSchema.model_validate(note) for note in notes]


@protected_route(
    router.get,
    "/{id}/notes/identifiers",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_note_identifiers(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> list[int]:
    """Get all note identifiers for a ROM."""
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    notes = db_rom_handler.get_rom_notes(
        rom_id=id,
        user_id=request.user.id,
        only_fields=[RomNote.id],
    )

    return [note.id for note in notes]


@protected_route(
    router.post,
    "/{id}/notes",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def create_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_data: Annotated[dict, Body()],
) -> UserNoteSchema:
    """Create a new note for a ROM."""
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    note = db_rom_handler.create_rom_note(
        rom_id=id,
        user_id=request.user.id,
        title=note_data["title"],
        content=note_data.get("content", ""),
        is_public=note_data.get("is_public", False),
        tags=note_data.get("tags", []),
    )

    # Add username to the note data
    note["username"] = request.user.username
    return UserNoteSchema.model_validate(note)


@protected_route(
    router.put,
    "/{id}/notes/{note_id}",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_id: Annotated[int, PathVar(description="Note id.", ge=1)],
    note_data: Annotated[dict, Body()],
) -> UserNoteSchema:
    """Update a ROM note."""
    note = db_rom_handler.update_rom_note(
        note_id=note_id,
        user_id=request.user.id,
        **{
            k: v
            for k, v in note_data.items()
            if k in ["title", "content", "is_public", "tags"]
        },
    )

    if not note:
        raise HTTPException(
            status_code=404, detail="Note not found or not owned by user"
        )

    # Add username to the note data
    note["username"] = request.user.username
    return UserNoteSchema.model_validate(note)


@protected_route(
    router.delete,
    "/{id}/notes/{note_id}",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_id: Annotated[int, PathVar(description="Note id.", ge=1)],
) -> dict:
    """Delete a ROM note."""
    success = db_rom_handler.delete_rom_note(note_id=note_id, user_id=request.user.id)

    if not success:
        raise HTTPException(
            status_code=404, detail="Note not found or not owned by user"
        )

    return {"message": "Note deleted successfully"}
