from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from decorators.auth import protected_route
from endpoints.responses.rom import DetailedRomSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.auth.constants import Scope
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler, fs_rom_handler
from handler.scan_handler import scan_platform
from logger.logger import log
from models.platform import Platform
from models.rom import Rom
from utils.filesystem import sanitize_filename
from utils.router import APIRouter

router = APIRouter()


class RomResolveRequest(BaseModel):
    platform_slug: str = Field(description="Canonical platform slug.", min_length=1)
    fs_name: str = Field(description="Client-side ROM filename.", min_length=1)
    crc_hash: str | None = Field(default=None, description="CRC32 hash of the ROM.")
    md5_hash: str | None = Field(default=None, description="MD5 hash of the ROM.")
    sha1_hash: str | None = Field(default=None, description="SHA1 hash of the ROM.")
    name: str | None = Field(default=None, description="Display name hint.")


async def _get_or_create_platform(fs_slug: str) -> Platform:
    platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
    if platform:
        return platform

    try:
        await fs_platform_handler.add_platform(fs_slug=fs_slug)
    except PlatformAlreadyExistsException:
        pass

    scanned_platform = await scan_platform(fs_slug, [fs_slug])
    return db_platform_handler.add_platform(scanned_platform)


@protected_route(
    router.post,
    "/resolve",
    [Scope.ROMS_WRITE],
)
async def resolve_rom(
    request: Request, payload: RomResolveRequest
) -> DetailedRomSchema:
    """Resolve a client-side ROM to a database entry, creating one if needed.

    Matches an existing rom on the platform first by hash, then by filesystem
    name. When nothing matches, a virtual (fileless) rom is created so sync
    clients can attach saves and states without the server holding the file.
    Idempotent: repeated calls with the same payload return the same rom.
    """
    platform = await _get_or_create_platform(payload.platform_slug)
    fs_name = sanitize_filename(payload.fs_name)

    rom = db_rom_handler.get_rom_by_hash(
        crc_hash=payload.crc_hash,
        md5_hash=payload.md5_hash,
        sha1_hash=payload.sha1_hash,
        platform_id=platform.id,
    )

    if not rom:
        rom = db_rom_handler.get_roms_by_fs_name(platform.id, [fs_name]).get(fs_name)

    if not rom:
        try:
            rom = db_rom_handler.add_rom(
                Rom(
                    platform_id=platform.id,
                    fs_name=fs_name,
                    fs_path=fs_rom_handler.get_roms_fs_structure(platform.fs_slug),
                    fs_size_bytes=0,
                    name=payload.name
                    or fs_rom_handler.get_file_name_with_no_tags(fs_name),
                    crc_hash=payload.crc_hash,
                    md5_hash=payload.md5_hash,
                    sha1_hash=payload.sha1_hash,
                    is_virtual=True,
                    url_cover="",
                    url_manual="",
                    url_screenshots=[],
                )
            )
            log.info(
                f"Created virtual rom '{rom.fs_name}' [ID: {rom.id}] "
                f"on platform '{platform.fs_slug}'"
            )
        except IntegrityError:
            # A concurrent resolve created the same (platform, fs_name) row.
            rom = db_rom_handler.get_roms_by_fs_name(platform.id, [fs_name]).get(
                fs_name
            )
            if not rom:
                raise

    resolved_rom = db_rom_handler.get_rom(rom.id)
    if not resolved_rom:
        raise RomNotFoundInDatabaseException(rom.id)

    return DetailedRomSchema.from_orm_with_request(resolved_rom, request)
