from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from decorators.auth import protected_route
from endpoints.responses.assets import StateSchema
from endpoints.roms import refresh_affected_smart_collections
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.asset_store import (
    remove_asset_file,
    remove_screenshot,
    rename_asset,
    store_screenshot,
    store_state_file,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_rom_handler, db_screenshot_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import build_asset_file_response
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import State
from models.base import FILE_NAME_MAX_LENGTH
from utils.assets import normalize_asset_labels
from utils.filesystem import sanitize_filename
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size
from utils.validation import RomIdScope, narrow_rom_id_scope


async def _delete_state(state: State) -> None:
    """Drop a state row with its file and screenshot."""
    db_state_handler.delete_state(state.id)
    await remove_asset_file(state.full_path, "State file")
    await remove_screenshot(state.screenshot)


def _owned_state_or_404(id: int, user_id: int) -> State:
    state = db_state_handler.get_state_by_id(id)
    if not state or state.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {id} not found",
        )
    return state


router = APIRouter(
    prefix="/states",
    tags=["states"],
)

STATE_FILE_UPLOAD = File(..., description="State file to upload.")
STATE_SCREENSHOT_UPLOAD = File(
    default=None,
    description="Screenshot file associated with this state.",
)
STATE_FILE_UPDATE = File(default=None, description="Updated state file content.")
STATE_SCREENSHOT_UPDATE = File(default=None, description="Updated screenshot file.")


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_state(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
    stateFile: UploadFile = STATE_FILE_UPLOAD,
    screenshotFile: UploadFile | None = STATE_SCREENSHOT_UPLOAD,
) -> StateSchema:
    check_asset_upload_size(stateFile, "State file")
    check_asset_upload_size(screenshotFile, "Screenshot file")

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    assert_rom_visible(request, rom)

    if not stateFile.filename:
        log.error("State file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="State file has no filename"
        )

    try:
        sanitized_state_filename = sanitize_filename(stateFile.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state filename: {str(exc)}",
        ) from exc

    log.info(
        f"Uploading state {hl(sanitized_state_filename)} for {hl(str(rom.name), color=BLUE)}"
    )

    db_state = await store_state_file(
        request.user, rom, emulator, stateFile, sanitized_state_filename
    )

    if screenshotFile and screenshotFile.filename:
        try:
            sanitized_screenshot_filename = sanitize_filename(screenshotFile.filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid screenshot filename: {str(exc)}",
            ) from exc

        await store_screenshot(
            request.user, rom, screenshotFile, sanitized_screenshot_filename
        )

    # Set the last played time for the current user
    rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    # Refetch the rom to get updated states
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    refresh_affected_smart_collections([rom.id], membership_only=True)

    return StateSchema.model_validate(db_state)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_states(
    request: Request,
    rom_id: int | None = None,
    rom_ids: Annotated[
        RomIdScope,
        Query(
            description=(
                "ROM IDs to scope the results to, for clients syncing a known "
                "set of ROMs. Multiple values are allowed by repeating the "
                "parameter. Combined with `rom_id` when both are given."
            ),
        ),
    ] = None,
    platform_id: int | None = None,
) -> list[StateSchema]:
    """Retrieve states for the current user."""
    states = db_state_handler.get_states(
        user_id=request.user.id,
        rom_ids=narrow_rom_id_scope(rom_id, rom_ids),
        platform_id=platform_id,
    )

    return [StateSchema.model_validate(state) for state in states]


@protected_route(router.get, "/identifiers", [Scope.ASSETS_READ])
def get_state_identifiers(
    request: Request,
) -> list[int]:
    """Get state identifiers endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[int]: List of state IDs
    """
    return db_state_handler.get_state_ids(user_id=request.user.id)


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_state(request: Request, id: int) -> StateSchema:
    state = db_state_handler.get_state(user_id=request.user.id, id=id)

    if not state:
        error = f"State with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return StateSchema.model_validate(state)


@protected_route(router.get, "/{id}/content", [Scope.ASSETS_READ])
def download_state(request: Request, id: int) -> FileResponse:
    """Download a state file. Owner can download any of their states; everyone
    else only public ones."""
    state = db_state_handler.get_state_by_id(id)
    if not state or (state.user_id != request.user.id and not state.is_public):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {id} not found",
        )

    # Sharing must not override the hidden-ROM/platform policy: a state on a ROM
    # hidden from the caller stays 404-masked, just like the ROM itself.
    assert_rom_visible(
        request, state.rom, not_found_detail=f"State with ID {id} not found"
    )

    try:
        file_path = fs_asset_handler.validate_path(state.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="State file not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="State file not found on disk",
        )

    return build_asset_file_response(file_path, filename=state.file_name)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_state(
    request: Request,
    id: int,
    stateFile: UploadFile | None = STATE_FILE_UPDATE,
    screenshotFile: UploadFile | None = STATE_SCREENSHOT_UPDATE,
) -> StateSchema:
    check_asset_upload_size(stateFile, "State file")
    check_asset_upload_size(screenshotFile, "Screenshot file")

    db_state = db_state_handler.get_state(user_id=request.user.id, id=id)
    if not db_state:
        error = f"State with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    if stateFile:
        await fs_asset_handler.write_file(
            file=stateFile, path=db_state.file_path, filename=db_state.file_name
        )
        db_state = db_state_handler.update_state(
            db_state.id, {"file_size_bytes": stateFile.size}
        )
    if screenshotFile and screenshotFile.filename:
        try:
            sanitized_screenshot_filename = sanitize_filename(screenshotFile.filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid screenshot filename: {str(exc)}",
            ) from exc

        await store_screenshot(
            request.user,
            db_state.rom,
            screenshotFile,
            sanitized_screenshot_filename,
        )

    # Set the last played time for the current user
    rom_user = db_rom_handler.get_rom_user(db_state.rom_id, request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(db_state.rom_id, request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    # Refetch the state to get updated fields
    return StateSchema.model_validate(db_state)


@protected_route(
    router.put,
    "/{id}/visibility",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_state_visibility(
    request: Request,
    id: int,
    is_public: Annotated[bool, Body(embed=True)],
) -> StateSchema:
    """Toggle a state's public/private visibility (owner only)."""
    state = _owned_state_or_404(id, request.user.id)

    updated = db_state_handler.update_state(id, {"is_public": is_public})

    # Keep the auto-captured thumbnail's visibility in sync so a shared state
    # still renders its preview for other users.
    if state.screenshot:
        db_screenshot_handler.update_screenshot(
            state.screenshot.id, {"is_public": is_public}
        )

    # Sharing a state exposes it to every other user's `has_states` filter.
    refresh_affected_smart_collections([state.rom_id], membership_only=True)

    return StateSchema.model_validate(updated)


@protected_route(
    router.put,
    "/{id}/favorite",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_state_favorite(
    request: Request,
    id: int,
    is_favorite: Annotated[bool, Body(embed=True)],
) -> StateSchema:
    """Favorite a state, sorting it ahead of the rest (owner only)."""
    _owned_state_or_404(id, request.user.id)

    return StateSchema.model_validate(
        db_state_handler.update_state(id, {"is_favorite": is_favorite}, touch=False)
    )


@protected_route(
    router.put,
    "/{id}/labels",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_state_labels(
    request: Request,
    id: int,
    labels: Annotated[list[str], Body(embed=True)],
) -> StateSchema:
    """Replace a state's free-text labels (owner only)."""
    _owned_state_or_404(id, request.user.id)

    return StateSchema.model_validate(
        db_state_handler.update_state(
            id, {"labels": normalize_asset_labels(labels)}, touch=False
        )
    )


@protected_route(
    router.put,
    "/{id}/file-name",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def rename_state(
    request: Request,
    id: int,
    file_name: Annotated[str, Body(embed=True, max_length=FILE_NAME_MAX_LENGTH)],
) -> StateSchema:
    """Rename a state's file, its screenshot following along (owner only)."""
    state = _owned_state_or_404(id, request.user.id)

    columns = await rename_asset(
        state,
        file_name,
        db_state_handler.get_states(user_id=request.user.id, rom_ids=[state.rom_id]),
    )

    return StateSchema.model_validate(
        db_state_handler.update_state(id, columns, touch=False)
    )


@protected_route(
    router.post,
    "/delete",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def delete_states(
    request: Request,
    states: Annotated[
        list[int],
        Body(
            description="List of states ids to delete from database.",
            embed=True,
        ),
    ],
) -> list[int]:
    """Delete states."""
    if not states:
        error = "No states were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    affected_rom_ids: set[int] = set()

    for state_id in states:
        state = db_state_handler.get_state(user_id=request.user.id, id=state_id)
        if not state:
            error = f"State with ID {state_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        affected_rom_ids.add(state.rom_id)
        log.info(
            f"Deleting state {hl(state.file_name)} [{state.rom.platform_slug}] from filesystem"
        )
        await _delete_state(state)

    refresh_affected_smart_collections(list(affected_rom_ids), membership_only=True)

    return states
