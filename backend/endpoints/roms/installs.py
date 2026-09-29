from typing import Annotated

from fastapi import Path as PathVar
from fastapi import Request, status

from config import DEVICE_INSTALL_ENABLED
from decorators.auth import protected_route
from endpoints.responses.device.install import InstallRequestSchema
from exceptions.endpoint_exceptions import (
    DeviceInstallDisabledException,
    RomNotFoundInDatabaseException,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_rom_handler
from handler.device_install import device_install_handler
from utils.router import APIRouter

router = APIRouter()


@protected_route(
    router.get,
    "/{id}/installs",
    [Scope.DEVICES_READ, Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_installs(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> list[InstallRequestSchema]:
    """The caller's pending and taken requests for a rom on any device, oldest first."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()

    rom = db_rom_handler.get_rom_visibility(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    return await device_install_handler.list_for_rom(request.user.id, id)
