from pydantic import BaseModel
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, status
from typing_extensions import TypedDict

from utils.oauth import protected_route
from handler import dbh
from utils.fs import build_upload_file_path
from utils.fastapi import scan_save
from logger.logger import log
from config.config_loader import config


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

class StateSchema(BaseAsset):
    rom_id: int
    platform_slug: str

class ScreenshotSchema(BaseAsset):
    rom_id: int

class BiosSchema(BaseAsset):
    platform_slug: str

class UploadAssetResponse(TypedDict):
    uploaded_assets: list[str]

@protected_route(router.put, "/saves/upload", ["assets.write"])
def upload_saves(
    request: Request, rom_id: str, saves: list[UploadFile] = File(...)
) -> UploadAssetResponse:
    rom = dbh.get_rom(rom_id)
    log.info(f"Uploading saves to {rom.name}")
    if saves is None: 
        log.error("No saves were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No saves were uploaded",
        )

    saves_path = build_upload_file_path(rom.platform_slug, folder=config.SAVES_FOLDER_NAME)
    uploaded_saves = []

    for save in saves:
        log.info(f" - Uploading {save.filename}")
        file_location = f"{saves_path}/{save.filename}"

        with open(file_location, "wb+") as f:
            while True:
                chunk = save.file.read(1024)
                if not chunk:
                    break
                f.write(chunk)

        uploaded_saves.append(save.filename)

        # Scan or update save
        scanned_save = scan_save(rom.platform, save.filename)
        db_save = dbh.get_save_by_filename(rom.platform_slug, save.filename)
        if db_save:
            dbh.update_save(db_save.id, { "file_size_bytes": scanned_save.file_size_bytes })
            continue

        scanned_save.rom_id = rom.id
        scanned_save.platform_slug = rom.platform_slug
        dbh.add_save(scanned_save)

    return {
        "uploaded_assets": uploaded_saves,
    }
