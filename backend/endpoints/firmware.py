from typing import Annotated

from fastapi import Body, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from config import DISABLE_DOWNLOAD_ENDPOINT_AUTH
from decorators.auth import protected_route
from endpoints.responses import BulkOperationResponse
from endpoints.responses.firmware import AddFirmwareResponse, FirmwareSchema
from handler.auth.constants import Scope
from handler.database import db_firmware_handler, db_platform_handler
from handler.filesystem import fs_firmware_handler
from handler.scan_handler import scan_firmware
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.firmware import Firmware
from utils.router import APIRouter

router = APIRouter(
    prefix="/firmware",
    tags=["firmware"],
)


@protected_route(router.post, "", [Scope.FIRMWARE_WRITE])
async def add_firmware(
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
        HTTPException

    Returns:
        AddFirmwareResponse: Standard message response
    """

    db_platform = db_platform_handler.get_platform(platform_id)
    if not db_platform:
        error = f"Platform with ID {platform_id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    uploaded_firmware = []
    firmware_path = fs_firmware_handler.get_firmware_fs_structure(db_platform.fs_slug)

    for file in files:
        if not file.filename:
            log.warning("Empty filename, skipping")
            continue

        log.info(
            f"Uploading firmware {hl(file.filename)} to {hl(db_platform.custom_name or db_platform.name, color=BLUE)}"
        )

        await fs_firmware_handler.write_file(file=file, path=firmware_path)

        db_firmware = db_firmware_handler.get_firmware_by_filename(
            platform_id=db_platform.id, file_name=file.filename
        )
        # Scan or update firmware
        scanned_firmware = await scan_firmware(
            platform=db_platform,
            file_name=file.filename,
            firmware=db_firmware,
        )

        is_verified = Firmware.verify_file_hashes(
            platform_slug=db_platform.slug,
            file_name=file.filename,
            file_size_bytes=scanned_firmware.file_size_bytes,
            md5_hash=scanned_firmware.md5_hash,
            sha1_hash=scanned_firmware.sha1_hash,
            crc_hash=scanned_firmware.crc_hash,
        )

        if db_firmware:
            db_firmware_handler.update_firmware(
                db_firmware.id,
                {
                    "file_size_bytes": scanned_firmware.file_size_bytes,
                    "is_verified": is_verified,
                },
            )
            continue

        scanned_firmware.platform_id = db_platform.id
        scanned_firmware.is_verified = is_verified
        db_firmware_handler.add_firmware(scanned_firmware)
        uploaded_firmware.append(scanned_firmware)

    return {
        "uploaded": len(files),
        "firmware": [
            FirmwareSchema.model_validate(f)
            for f in db_firmware_handler.list_firmware(platform_id=platform_id)
        ],
    }


@protected_route(router.get, "", [Scope.FIRMWARE_READ])
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
    return [
        FirmwareSchema.model_validate(f)
        for f in db_firmware_handler.list_firmware(platform_id=platform_id)
    ]


@protected_route(
    router.get,
    "/{id}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.FIRMWARE_READ],
)
def get_firmware(request: Request, id: int) -> FirmwareSchema:
    """Get firmware endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Firmware internal id

    Returns:
        FirmwareSchema: Firmware stored in the database
    """
    firmware = db_firmware_handler.get_firmware(id)
    if not firmware:
        error = f"Firmware with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return FirmwareSchema.model_validate(firmware)


@protected_route(
    router.head,
    "/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.FIRMWARE_READ],
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
    if not firmware:
        error = f"Firmware with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    firmware_path = fs_firmware_handler.validate_path(firmware.full_path)

    return FileResponse(
        path=firmware_path,
        filename=file_name,
        headers={
            "Content-Length": str(firmware.file_size_bytes),
        },
    )


@protected_route(
    router.get,
    "/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.FIRMWARE_READ],
)
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
    if not firmware:
        error = f"Firmware with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    firmware_path = fs_firmware_handler.validate_path(firmware.full_path)

    return FileResponse(path=firmware_path, filename=firmware.file_name)


@protected_route(router.post, "/delete", [Scope.FIRMWARE_WRITE])
async def delete_firmware(
    request: Request,
    firmware: Annotated[
        list[int],
        Body(
            description="List of firmware ids to delete from database.",
            embed=True,
        ),
    ],
    delete_from_fs: Annotated[
        list[int],
        Body(
            description="List of firmware ids to delete from filesystem.",
            default_factory=list,
            embed=True,
        ),
    ],
) -> BulkOperationResponse:
    """Delete firmware."""

    successful_items = 0
    failed_items = 0
    errors = []

    for id in firmware:
        fw = db_firmware_handler.get_firmware(id)
        if not fw:
            failed_items += 1
            errors.append(f"Firmware with ID {id} not found")
            continue

        try:
            log.info(f"Deleting {hl(fw.file_name)} from database")
            db_firmware_handler.delete_firmware(id)

            if id in delete_from_fs:
                log.info(f"Deleting {hl(fw.file_name)} from filesystem")
                try:
                    file_path = f"{fw.file_path}/{fw.file_name}"
                    await fs_firmware_handler.remove_file(file_path=file_path)
                except FileNotFoundError:
                    error = f"Firmware file {hl(fw.file_name)} not found for platform {hl(fw.platform.slug)}"
                    log.error(error)
                    errors.append(error)
                    failed_items += 1
                    continue

            successful_items += 1
        except Exception as e:
            failed_items += 1
            errors.append(f"Failed to delete firmware {id}: {str(e)}")

    return {
        "successful_items": successful_items,
        "failed_items": failed_items,
        "errors": errors,
    }
