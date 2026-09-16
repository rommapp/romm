"""Filing a state or screenshot: write the bytes, scan them, upsert the row.

Shared by the upload routes and the streaming sync. What differs between them
(dedup, retention, where the bytes came from) stays with the caller.
"""

from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, TypeAlias

from fastapi import UploadFile

from handler.database import db_screenshot_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_screenshot, scan_state
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Screenshot, State
from models.rom import Rom
from models.user import User

# What `fs_asset_handler.write_file` accepts: an upload straight off a request,
# or bytes a sync already holds.
AssetContent: TypeAlias = UploadFile | BinaryIO | BytesIO | bytes | SpooledTemporaryFile


async def store_state_file(
    user: User,
    rom: Rom,
    emulator: str | None,
    content: AssetContent,
    filename: str,
    fields: dict[str, Any] | None = None,
) -> State:
    """Write a state file and file its row, updating one already at that name.

    The row follows the bytes: writing under a different emulator moves both and
    the file left at the old location goes. `fields` carries columns only one
    caller owns, so a caller that does not set them never clears them.
    """
    states_path = fs_asset_handler.build_states_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    await fs_asset_handler.write_file(file=content, path=states_path, filename=filename)

    scanned = await scan_state(
        file_name=filename,
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    existing = db_state_handler.get_state_by_filename(
        user_id=user.id, rom_id=rom.id, file_name=filename
    )
    if existing is None:
        scanned.rom_id = rom.id
        scanned.user_id = user.id
        scanned.emulator = emulator
        for key, value in (fields or {}).items():
            setattr(scanned, key, value)
        return db_state_handler.add_state(state=scanned)

    stale_full_path = existing.full_path
    updated = db_state_handler.update_state(
        existing.id,
        {
            "file_size_bytes": scanned.file_size_bytes,
            "file_path": scanned.file_path,
            "emulator": emulator,
            **(fields or {}),
        },
    )
    if stale_full_path != updated.full_path:
        try:
            await fs_asset_handler.remove_file(stale_full_path)
        except FileNotFoundError:
            pass
    return updated


async def store_screenshot(
    user: User, rom: Rom, content: AssetContent, filename: str
) -> Screenshot:
    """Write a screenshot and file its row, updating one already at that name.

    `State.screenshot` matches by filename stem, so a state thumbnail binds
    itself by reusing the state's stem with a .png extension.
    """
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
    )
    await fs_asset_handler.write_file(
        file=content, path=screenshots_path, filename=filename
    )

    scanned = await scan_screenshot(
        file_name=filename,
        user=user,
        platform_fs_slug=rom.platform_slug,
        rom_id=rom.id,
    )
    existing = db_screenshot_handler.get_screenshot(
        file_name=filename, rom_id=rom.id, user_id=user.id
    )
    if existing is None:
        scanned.rom_id = rom.id
        scanned.user_id = user.id
        return db_screenshot_handler.add_screenshot(screenshot=scanned)

    return db_screenshot_handler.update_screenshot(
        existing.id, {"file_size_bytes": scanned.file_size_bytes}
    )


async def remove_asset_file(file_path: str, what: str) -> None:
    """Remove an asset file; one already gone is only logged."""
    try:
        await fs_asset_handler.remove_file(file_path=file_path)
    except FileNotFoundError:
        log.error(f"{what} {hl(file_path)} not found on disk")


async def remove_screenshot(screenshot: Screenshot | None) -> None:
    """Drop a save's or state's screenshot row and file, if it has one."""
    if not screenshot:
        return
    db_screenshot_handler.delete_screenshot(screenshot.id)
    await remove_asset_file(
        f"{screenshot.file_path}/{screenshot.file_name}", "Screenshot file"
    )
