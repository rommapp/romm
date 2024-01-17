from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.assets import UploadedStatesResponse
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from handler import dbstateh, dbromh, fsasseth
from handler.scan_handler import scan_state
from logger.logger import log

router = APIRouter()


@protected_route(router.post, "/states", ["assets.write"])
def add_states(
    request: Request, rom_id: int, states: list[UploadFile] = File(...)
) -> UploadedStatesResponse:
    rom = dbromh.get_roms(rom_id)
    log.info(f"Uploading states to {rom.name}")
    if states is None:
        log.error("No states were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No states were uploaded",
        )

    states_path = fsasseth.build_upload_file_path(
        rom.platform.fs_slug, folder=cm.config.STATES_FOLDER_NAME
    )

    for state in states:
        fsasseth._write_file(file=state, path=states_path)

        # Scan or update state
        scanned_state = scan_state(rom.platform, state.filename)
        db_state = dbstateh.get_state(rom.id)
        if db_state:
            dbstateh.update_state(
                db_state.id, {"file_size_bytes": scanned_state.file_size_bytes}
            )
            continue

        scanned_state.rom_id = rom.id
        dbstateh.add_state(scanned_state)

    return {"uploaded": len(states), "states": rom.states}


@protected_route(router.get, "/states", ["assets.read"])
def get_states(request: Request) -> MessageResponse:
    pass


@protected_route(router.get, "/states/{id}", ["assets.read"])
def get_save(request: Request, id: int) -> MessageResponse:
    pass


@protected_route(router.put, "/states/{id}", ["assets.write"])
def update_save(request: Request, id: int) -> MessageResponse:
    pass


@protected_route(router.post, "/states/delete", ["assets.write"])
async def delete_states(request: Request) -> MessageResponse:
    data: dict = await request.json()
    state_ids: list = data["states"]
    delete_from_fs: bool = data["delete_from_fs"]

    if not state_ids:
        error = "No states were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for state_id in state_ids:
        state = dbstateh.get_state(state_id)
        if not state:
            error = f"Save with ID {state_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        dbstateh.delete_state(state_id)

        if delete_from_fs:
            log.info(f"Deleting {state.file_name} from filesystem")
            try:
                fsasseth.remove_file(
                    file_name=state.file_name, file_path=state.file_path
                )
            except FileNotFoundError:
                error = f"Save file {state.file_name} not found for platform {state.rom.platform_slug}"
                log.error(error)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {"msg": f"Successfully deleted {len(state_ids)} states."}
