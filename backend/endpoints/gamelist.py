from typing import Annotated, List

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import Response

from decorators.auth import protected_route
from handler.auth.constants import Scope
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.gamelist_exporter import GamelistExporter
from utils.router import APIRouter

router = APIRouter(
    prefix="/gamelist",
    tags=["gamelist"],
)


@protected_route(router.post, "/export", [Scope.ROMS_READ])
async def export_gamelist(
    request: Request,
    platform_ids: Annotated[
        List[int], Query(description="List of platform IDs to export")
    ],
    local_export: Annotated[
        bool, Query(description="Use local paths instead of URLs")
    ] = False,
) -> Response:
    """Export platforms/ROMs to gamelist.xml format and write to platform directories"""
    if not platform_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one platform ID must be provided",
        )

    try:
        exporter = GamelistExporter(local_export=local_export)
        files_written = []

        # Export each platform to its respective directory
        for platform_id in platform_ids:
            success = await exporter.export_platform_to_file(
                platform_id,
                request,
            )
            if success:
                files_written.append(f"gamelist_{platform_id}.xml")
            else:
                log.warning(f"Failed to write gamelist for platform {platform_id}")

        if not files_written:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to write any gamelist files",
            )

        log.info(
            f"Exported gamelist for {hl(str(len(files_written)), color=BLUE)} platform(s):"
        )
        for file in files_written:
            log.info(f"\t• {file}")
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        log.error(f"Failed to export gamelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export gamelist",
        ) from e
