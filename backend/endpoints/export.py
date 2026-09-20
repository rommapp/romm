from typing import Annotated, List

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import Response

from decorators.auth import protected_route
from exceptions.endpoint_exceptions import PlatformNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_platform_visible
from handler.database import db_platform_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.gamelist_exporter import GamelistExporter
from utils.pegasus_exporter import PegasusExporter
from utils.router import APIRouter

router = APIRouter(
    prefix="/export",
    tags=["export"],
)


def _assert_platforms_exportable(request: Request, platform_ids: List[int]) -> None:
    """Reject the whole request before anything is written to disk.

    A platform hidden from the caller 404s exactly like a missing one, so the
    response never reveals that the platform exists.
    """
    for platform_id in platform_ids:
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise PlatformNotFoundInDatabaseException(platform_id)
        assert_platform_visible(request, platform)


@protected_route(router.post, "/gamelist-xml", [Scope.PLATFORMS_WRITE])
async def export_gamelist_xml(
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

    _assert_platforms_exportable(request, platform_ids)

    try:
        exporter = GamelistExporter(local_export=local_export)
        files_written = []

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


@protected_route(router.post, "/pegasus", [Scope.PLATFORMS_WRITE])
async def export_pegasus(
    request: Request,
    platform_ids: Annotated[
        List[int], Query(description="List of platform IDs to export")
    ],
    local_export: Annotated[
        bool, Query(description="Use local paths instead of URLs")
    ] = False,
) -> Response:
    """Export platforms/ROMs to Pegasus metadata.pegasus.txt format and write to platform directories"""
    if not platform_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one platform ID must be provided",
        )

    _assert_platforms_exportable(request, platform_ids)

    try:
        exporter = PegasusExporter(local_export=local_export)
        files_written = []

        for platform_id in platform_ids:
            success = await exporter.export_platform_to_file(
                platform_id,
                request,
            )
            if success:
                files_written.append(f"metadata_pegasus_{platform_id}.txt")
            else:
                log.warning(
                    f"Failed to write Pegasus metadata for platform {platform_id}"
                )

        if not files_written:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to write any Pegasus metadata files",
            )

        log.info(
            f"Exported Pegasus metadata for {hl(str(len(files_written)), color=BLUE)} platform(s):"
        )
        for file in files_written:
            log.info(f"\t• {file}")
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        log.error(f"Failed to export Pegasus metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export Pegasus metadata",
        ) from e
