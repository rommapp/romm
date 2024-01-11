from pathlib import Path
from typing import Optional

from config.config_manager import config_manager
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from handler import dbh
from logger.logger import log
from pydantic import BaseModel
from typing_extensions import TypedDict
from utils.fastapi import scan_save, scan_state
from utils.fs import build_upload_file_path, remove_file
from utils.oauth import protected_route

router = APIRouter()


class BaseAsset(BaseModel):
    id: int

    file_name: str
    file_name_no_tags: str
    file_extension: str
    file_path: str
    file_size_bytes: int
    full_path: str
    download_path: str

    class Config:
        from_attributes = True


class SaveSchema(BaseAsset):
    rom_id: int
    platform_slug: str
    emulator: Optional[str]


class StateSchema(BaseAsset):
    rom_id: int
    platform_slug: str
    emulator: Optional[str]


class ScreenshotSchema(BaseAsset):
    rom_id: int
    platform_slug: Optional[str]


class UploadedSavesResponse(TypedDict):
    uploaded: int
    saves: list[SaveSchema]


class UploadedStatesResponse(TypedDict):
    uploaded: int
    states: list[StateSchema]


def write_file(file: UploadFile, path: str) -> None:
    log.info(f" - Uploading {file.filename}")
    file_location = f"{path}/{file.filename}"
    Path(path).mkdir(parents=True, exist_ok=True)

    with open(file_location, "wb+") as f:
        while True:
            chunk = file.file.read(1024)
            if not chunk:
                break
            f.write(chunk)


@protected_route(router.put, "/saves/upload", ["assets.write"])
def upload_saves(
    request: Request, rom_id: str, saves: list[UploadFile] = File(...)
) -> UploadedSavesResponse:
    rom = dbh.get_rom(rom_id)
    log.info(f"Uploading saves to {rom.name}")
    if saves is None:
        log.error("No saves were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No saves were uploaded",
        )

    saves_path = build_upload_file_path(
        rom.platform.fs_slug, folder=config_manager.config.SAVES_FOLDER_NAME
    )

    for save in saves:
        write_file(file=save, path=saves_path)

        # Scan or update save
        scanned_save = scan_save(rom.platform, save.filename)
        db_save = dbh.get_save_by_filename(rom.platform_slug, save.filename)
        if db_save:
            dbh.update_save(
                db_save.id, {"file_size_bytes": scanned_save.file_size_bytes}
            )
            continue

        scanned_save.rom_id = rom.id
        scanned_save.platform_slug = rom.platform_slug
        dbh.add_save(scanned_save)

    rom = dbh.get_rom(rom_id)
    return {"uploaded": len(saves), "saves": rom.saves}


@protected_route(router.post, "/saves/delete", ["assets.write"])
async def delete_saves(request: Request) -> list[SaveSchema]:
    data: dict = await request.json()
    save_ids: list = data["saves"]
    delete_from_fs: bool = data["delete_from_fs"]

    if not save_ids:
        error = "No saves were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for save_id in save_ids:
        save = dbh.get_save(save_id)
        if not save:
            error = f"Save with ID {save_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        dbh.delete_save(save_id)

        if delete_from_fs:
            log.info(f"Deleting {save.file_name} from filesystem")

            try:
                remove_file(file_name=save.file_name, file_path=save.file_path)
            except FileNotFoundError:
                error = f"Save file {save.file_name} not found for platform {save.platform_slug}"
                log.error(error)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    rom = dbh.get_rom(save.rom_id)
    return rom.saves


@protected_route(router.put, "/states/upload", ["assets.write"])
def upload_states(
    request: Request, rom_id: str, states: list[UploadFile] = File(...)
) -> UploadedStatesResponse:
    rom = dbh.get_rom(rom_id)
    log.info(f"Uploading states to {rom.name}")
    if states is None:
        log.error("No states were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No states were uploaded",
        )

    states_path = build_upload_file_path(
        rom.platform.fs_slug, folder=config_manager.config.STATES_FOLDER_NAME
    )

    for state in states:
        write_file(file=state, path=states_path)

        # Scan or update state
        scanned_state = scan_state(rom.platform, state.filename)
        db_state = dbh.get_state_by_filename(rom.platform_slug, state.filename)
        if db_state:
            dbh.update_state(
                db_state.id, {"file_size_bytes": scanned_state.file_size_bytes}
            )
            continue

        scanned_state.rom_id = rom.id
        scanned_state.platform_slug = rom.platform_slug
        dbh.add_state(scanned_state)

    rom = dbh.get_rom(rom_id)
    return {"uploaded": len(states), "states": rom.states}


@protected_route(router.post, "/states/delete", ["assets.write"])
async def delete_states(request: Request) -> list[StateSchema]:
    data: dict = await request.json()
    state_ids: list = data["states"]
    delete_from_fs: bool = data["delete_from_fs"]

    if not state_ids:
        error = "No states were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for state_id in state_ids:
        state = dbh.get_state(state_id)
        if not state:
            error = f"Save with ID {state_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        dbh.delete_state(state_id)

        if delete_from_fs:
            log.info(f"Deleting {state.file_name} from filesystem")
            try:
                remove_file(file_name=state.file_name, file_path=state.file_path)
            except FileNotFoundError:
                error = f"Save file {state.file_name} not found for platform {state.platform_slug}"
                log.error(error)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    rom = dbh.get_rom(state.rom_id)
    return rom.states
