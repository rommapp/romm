from typing import Annotated, List, Optional

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.export.gamelist_exporter import GamelistExporter
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/gamelist",
    tags=["gamelist"],
)


class GamelistExportRequest(BaseModel):
    platform_ids: List[int]
    rom_ids: Optional[List[int]] = None


@protected_route(router.post, "/export", [Scope.ROMS_READ])
async def export_gamelist(
    request: Request,
    platform_ids: Annotated[
        List[int], Query(description="List of platform IDs to export")
    ],
    rom_ids: Annotated[
        Optional[List[int]],
        Query(description="Optional list of specific ROM IDs to export"),
    ] = None,
) -> Response:
    """Export platforms/ROMs to gamelist.xml format"""

    if not platform_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one platform ID must be provided",
        )

    try:
        exporter = GamelistExporter()

        # If only one platform, return single XML
        if len(platform_ids) == 1:
            platform_id = platform_ids[0]
            xml_content = exporter.export_platform(platform_id, rom_ids)

            log.info(
                f"Exported gamelist for platform {hl(str(platform_id), color=BLUE)} "
                f"with {hl(str(len(rom_ids) if rom_ids else 'all'), color=BLUE)} ROMs"
            )

            return Response(
                content=xml_content,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=gamelist_{platform_id}.xml"
                },
            )
        else:
            # Multiple platforms - return as zip or individual files
            # For now, return the first platform's XML
            # TODO: Implement zip export for multiple platforms
            platform_id = platform_ids[0]
            xml_content = exporter.export_platform(platform_id, rom_ids)

            log.info(
                f"Exported gamelist for platform {hl(str(platform_id), color=BLUE)} "
                f"(first of {len(platform_ids)} platforms)"
            )

            return Response(
                content=xml_content,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=gamelist_{platform_id}.xml"
                },
            )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        log.error(f"Failed to export gamelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export gamelist",
        ) from e


@protected_route(router.post, "/export/platform/{platform_id}", [Scope.ROMS_READ])
async def export_platform_gamelist(
    request: Request,
    platform_id: int,
    rom_ids: Annotated[
        Optional[List[int]],
        Query(description="Optional list of specific ROM IDs to export"),
    ] = None,
) -> Response:
    """Export a specific platform to gamelist.xml format"""

    try:
        exporter = GamelistExporter()
        xml_content = exporter.export_platform(platform_id, rom_ids)

        log.info(
            f"Exported gamelist for platform {hl(str(platform_id), color=BLUE)} "
            f"with {hl(str(len(rom_ids) if rom_ids else 'all'), color=BLUE)} ROMs"
        )

        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=gamelist_{platform_id}.xml"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        log.error(f"Failed to export platform gamelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export platform gamelist",
        ) from e


@protected_route(
    router.get, "/export/platform/{platform_id}/preview", [Scope.ROMS_READ]
)
async def preview_platform_gamelist(
    request: Request,
    platform_id: int,
    rom_ids: Annotated[
        Optional[List[int]],
        Query(description="Optional list of specific ROM IDs to preview"),
    ] = None,
) -> dict:
    """Preview gamelist export for a platform (returns metadata without full XML)"""

    try:
        from handler.database import db_platform_handler, db_rom_handler

        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Platform with ID {platform_id} not found",
            )

        # Get ROMs for the platform
        if rom_ids:
            roms = [db_rom_handler.get_rom(rom_id) for rom_id in rom_ids]
            roms = [rom for rom in roms if rom and rom.platform_id == platform_id]
        else:
            roms = db_rom_handler.get_roms_scalar(platform_id=platform_id)

        # Return preview metadata
        return {
            "platform": {
                "id": platform.id,
                "name": platform.name,
                "fs_slug": platform.fs_slug,
            },
            "rom_count": len(roms),
            "roms": [
                {
                    "id": rom.id,
                    "name": rom.name or rom.fs_name,
                    "fs_name": rom.fs_name,
                    "has_cover": bool(rom.url_cover),
                    "has_screenshots": bool(rom.url_screenshots),
                    "has_summary": bool(rom.summary),
                }
                for rom in roms
                if rom and not rom.missing_from_fs
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to preview platform gamelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview platform gamelist",
        ) from e
