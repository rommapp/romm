"""The kinds of console RomM syncs saves with over FTP, by device client."""

from typing import Literal

from handler.sync.console.common import ConsoleProfile
from handler.sync.console.ps3 import PS3
from handler.sync.console.ps4 import PS4
from models.device import Device

ConsoleKind = Literal["ps3", "ps4"]

CONSOLE_PROFILES: dict[str, ConsoleProfile] = {p.kind: p for p in (PS3, PS4)}


def profile_of_client(client: str | None) -> ConsoleProfile | None:
    return CONSOLE_PROFILES.get(client) if client else None


def is_console_client(client: str | None) -> bool:
    """Whether a device client is a console, which only the console routes manage."""
    return profile_of_client(client) is not None


def profile_of(device: Device) -> ConsoleProfile | None:
    return profile_of_client(device.client)


def is_console(device: Device) -> bool:
    return profile_of(device) is not None
