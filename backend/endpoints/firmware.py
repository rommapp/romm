from config import DISABLE_DOWNLOAD_ENDPOINT_AUTH, LIBRARY_BASE_PATH
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.firmware import AddFirmwareResponse, FirmwareSchema
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from handler.database import db_firmware_handler, db_platform_handler
from handler.filesystem import fs_firmware_handler
from handler.scan_handler import scan_firmware
from logger.logger import log

router = APIRouter()


@protected_route(router.post, "/firmware", ["firmware.write"])
def add_firmware(
    request: Request,
    platform_id: int,
    files: list[UploadFile] = File(...),  # noqa: B008
) -> AddFirmwareResponse:
    """Upload firmware files endpoint

    Args:
        request (Request): Fastapi Request object
        platform_slug (str): Slug of the platform where to upload the files
        files (list[UploadFile], optional): List of files to upload

    Raises:
        HTTPException: No files were uploaded

    Returns:
        AddFirmwareResponse: Standard message response
    """

    db_platform = db_platform_handler.get_platform(platform_id)
    log.info(f"Uploading firmware to {db_platform.fs_slug}")
    if files is None:
        log.error("No files were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No files were uploaded",
        )

    uploaded_firmware = []
    firmware_path = fs_firmware_handler.build_upload_file_path(db_platform.fs_slug)

    for file in files:
        fs_firmware_handler.write_file(file=file, path=firmware_path)

        db_firmware = db_firmware_handler.get_firmware_by_filename(
            platform_id=db_platform.id, file_name=file.filename
        )
        # Scan or update firmware
        scanned_firmware = scan_firmware(
            platform=db_platform,
            file_name=file.filename,
            firmware=db_firmware,
        )

        if db_firmware:
            db_firmware_handler.update_firmware(
                db_firmware.id, {"file_size_bytes": scanned_firmware.file_size_bytes}
            )
            continue

        scanned_firmware.platform_id = db_platform.id
        db_firmware_handler.add_firmware(scanned_firmware)
        uploaded_firmware.append(scanned_firmware)

    db_platform = db_platform_handler.get_platform(platform_id)

    return {
        "uploaded": len(files),
        "firmware": db_platform.firmware,
    }


@protected_route(router.get, "/firmware", ["firmware.read"])
def get_platform_firmware(
    request: Request,
    platform_id: int | None = None,
) -> list[FirmwareSchema]:
    """Get firmware endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[FirmwareSchema]: Firmware stored in the database
    """
    return db_firmware_handler.list_firmware(platform_id=platform_id)


@protected_route(
    router.get,
    "/firmware/{id}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["firmware.read"],
)
def get_firmware(request: Request, id: int) -> FirmwareSchema:
    """Get firmware endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Firmware internal id

    Returns:
        FirmwareSchema: Firmware stored in the database
    """
    return FirmwareSchema(**db_firmware_handler.get_firmware(id))


@protected_route(
    router.head,
    "/firmware/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["firmware.read"],
)
def head_firmware_content(request: Request, id: int, file_name: str):
    """Head firmware content endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        file_name (str): Required due to a bug in emulatorjs

    Returns:
        FileResponse: Returns the response with headers
    """

    firmware = db_firmware_handler.get_firmware(id)
    firmware_path = f"{LIBRARY_BASE_PATH}/{firmware.full_path}"

    return FileResponse(
        path=firmware_path,
        filename=file_name,
        headers={
            "Content-Length": str(firmware.file_size_bytes),
        },
    )


@protected_route(router.get, "/firmware/{id}/content/{file_name}", ["firmware.read"])
def get_firmware_content(
    request: Request,
    id: int,
    file_name: str,
):
    """Download firmware endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        file_name (str): Required due to a bug in emulatorjs

    Returns:
        FileResponse: Returns the firmware file
    """

    firmware = db_firmware_handler.get_firmware(id)
    firmware_path = f"{LIBRARY_BASE_PATH}/{firmware.full_path}"

    return FileResponse(path=firmware_path, filename=firmware.file_name)


@protected_route(router.post, "/firmware/delete", ["firmware.write"])
async def delete_firmware(
    request: Request,
) -> MessageResponse:
    """Delete firmware endpoint

    Args:
        request (Request): Fastapi Request object.
            {
                "firmware": List of firmware IDs to delete
            }
        delete_from_fs (bool, optional): Flag to delete rom from filesystem. Defaults to False.

    Returns:
        MessageResponse: Standard message response
    """

    data: dict = await request.json()
    firmare_ids: list = data["firmware"]
    delete_from_fs: list = data["delete_from_fs"]

    for id in firmare_ids:
        firmware = db_firmware_handler.get_firmware(id)
        if not firmware:
            error = f"Firmware with ID {id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        log.info(f"Deleting {firmware.file_name} from database")
        db_firmware_handler.delete_firmware(id)

        if id in delete_from_fs:
            log.info(f"Deleting {firmware.file_name} from filesystem")
            try:
                fs_firmware_handler.remove_file(
                    file_name=firmware.file_name, file_path=firmware.file_path
                )
            except FileNotFoundError as exc:
                error = f"Firmware file {firmware.file_name} not found for platform {firmware.platform_slug}"
                log.error(error)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=error
                ) from exc

    return {"msg": f"{len(firmare_ids)} firmware files deleted successfully!"}
