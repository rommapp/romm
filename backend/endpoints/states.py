from datetime import datetime, timezone

from decorators.auth import protected_route
from endpoints.responses.assets import StateSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from fastapi import HTTPException, Request, UploadFile, status
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_screenshot_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_screenshot, scan_state
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/states",
    tags=["states"],
)


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_state(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
) -> StateSchema:
    data = await request.form()

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    log.info(f"Uploading state of {rom.name}")

    states_path = fs_asset_handler.build_states_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )

    if "stateFile" not in data:
        log.error("No state file provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No state file provided"
        )

    stateFile: UploadFile = data["stateFile"]  # type: ignore

    if not stateFile.filename:
        log.error("State file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="State file has no filename"
        )

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    log.info(f"Uploading state {hl(stateFile.filename)} for {hl(rom.name, color=BLUE)}")

    states_path = fs_asset_handler.build_states_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    fs_asset_handler.write_file(file=stateFile, path=states_path)

    # Scan or update state
    scanned_state = scan_state(
        file_name=stateFile.filename,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )
    db_state = db_state_handler.get_state_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=stateFile.filename
    )
    if db_state:
        db_state = db_state_handler.update_state(
            db_state.id, {"file_size_bytes": scanned_state.file_size_bytes}
        )
    else:
        scanned_state.rom_id = rom.id
        scanned_state.user_id = request.user.id
        scanned_state.emulator = emulator
        db_state = db_state_handler.add_state(state=scanned_state)

    screenshotFile: UploadFile | None = data.get("screenshotFile", None)  # type: ignore
    if screenshotFile and screenshotFile.filename:
        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
        )

        fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=rom.platform_slug,
            rom_id=rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot_by_filename(
            rom_id=rom.id, user_id=request.user.id, file_name=screenshotFile.filename
        )
        if db_screenshot:
            db_screenshot = db_screenshot_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
        else:
            scanned_screenshot.rom_id = rom.id
            scanned_screenshot.user_id = request.user.id
            db_screenshot = db_screenshot_handler.add_screenshot(
                screenshot=scanned_screenshot
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

    return StateSchema.model_validate(db_state)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_states(
    request: Request, rom_id: int | None = None, platform_id: int | None = None
) -> list[StateSchema]:
    states = db_state_handler.get_states(
        user_id=request.user.id, rom_id=rom_id, platform_id=platform_id
    )

    return [StateSchema.model_validate(state) for state in states]


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_state(request: Request, id: int) -> StateSchema:
    state = db_state_handler.get_state(user_id=request.user.id, id=id)

    if not state:
        error = f"State with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return StateSchema.model_validate(state)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_state(request: Request, id: int) -> StateSchema:
    data = await request.form()

    db_state = db_state_handler.get_state(user_id=request.user.id, id=id)
    if not db_state:
        error = f"State with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    if "stateFile" in data:
        stateFile: UploadFile = data["stateFile"]  # type: ignore
        fs_asset_handler.write_file(file=stateFile, path=db_state.file_path)
        db_state = db_state_handler.update_state(
            db_state.id, {"file_size_bytes": stateFile.size}
        )

    screenshotFile: UploadFile | None = data.get("screenshotFile", None)  # type: ignore
    if screenshotFile and screenshotFile.filename:
        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user,
            platform_fs_slug=db_state.rom.platform_slug,
            rom_id=db_state.rom.id,
        )

        fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=db_state.rom.platform_slug,
            rom_id=db_state.rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot_by_filename(
            rom_id=db_state.rom.id,
            user_id=request.user.id,
            file_name=screenshotFile.filename,
        )
        if db_screenshot:
            db_screenshot = db_screenshot_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
        else:
            scanned_screenshot.rom_id = db_state.rom.id
            scanned_screenshot.user_id = request.user.id
            db_screenshot = db_screenshot_handler.add_screenshot(
                screenshot=scanned_screenshot
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


@protected_route(router.post, "/delete", [Scope.ASSETS_WRITE])
async def delete_states(request: Request) -> list[int]:
    data: dict = await request.json()
    state_ids: list = data["states"]

    if not state_ids:
        error = "No states were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for state_id in state_ids:
        state = db_state_handler.get_state(user_id=request.user.id, id=state_id)
        if not state:
            error = f"State with ID {state_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        db_state_handler.delete_state(state_id)
        log.info(
            f"Deleting state {hl(state.file_name)} [{state.rom.platform_slug}] from filesystem"
        )

        try:
            fs_asset_handler.remove_file(
                file_name=state.file_name, file_path=state.file_path
            )
        except FileNotFoundError:
            error = f"State file {hl(state.file_name)} not found for platform {hl(state.rom.platform_display_name, color=BLUE)}[{hl(state.rom.platform_slug)}]"
            log.error(error)

        if state.screenshot:
            db_screenshot_handler.delete_screenshot(state.screenshot.id)

            try:
                fs_asset_handler.remove_file(
                    file_name=state.screenshot.file_name,
                    file_path=state.screenshot.file_path,
                )
            except FileNotFoundError:
                error = f"Screenshot file {hl(state.screenshot.file_name)} not found for state {hl(state.file_name)}[{hl(state.rom.platform_slug)}]"
                log.error(error)

    return state_ids
