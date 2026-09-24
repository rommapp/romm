"""Filing a state or screenshot: write the bytes, scan them, upsert the row.

Shared by the upload routes and the streaming sync. What differs between them
(dedup, retention, where the bytes came from) stays with the caller. Renaming
a save or state lives here too, since its thumbnail has to follow the name.
"""

import os
from collections.abc import Iterable
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, TypeAlias

from fastapi import HTTPException, UploadFile, status

from handler.database import db_screenshot_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_screenshot, scan_state
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.base import compute_file_name_no_ext, compute_file_name_parts
from models.rom import Rom
from models.user import User
from utils.filesystem import sanitize_filename

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


def _file_name_columns(file_name: str) -> dict[str, str]:
    """A file name with the columns derived from it, which a bulk update() must
    write itself since it skips the `@validates` hook."""
    parts = compute_file_name_parts(file_name)
    return {
        "file_name": file_name,
        "file_name_no_tags": parts.no_tags,
        "file_name_no_ext": parts.no_ext,
        "file_extension": parts.extension,
    }


def _name_taken(file_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"{file_name} already exists",
    )


async def _move_asset_files(
    asset: Save | State,
    new_name: str,
    thumbnail: Screenshot | None,
    thumbnail_name: str,
) -> None:
    """Rename an asset's file, then its thumbnail's, undoing the first if the
    second fails."""
    await fs_asset_handler.rename_file(asset.full_path, new_name)
    if thumbnail is None:
        return
    try:
        await fs_asset_handler.rename_file(
            f"{thumbnail.file_path}/{thumbnail.file_name}", thumbnail_name
        )
    except FileNotFoundError:
        # Only the row is left to rename, so the asset stays bound to it.
        pass
    except Exception:
        await fs_asset_handler.rename_file(
            f"{asset.file_path}/{new_name}", asset.file_name
        )
        raise


async def rename_asset(
    asset: Save | State, file_name: str, siblings: Iterable[Save | State]
) -> dict[str, str]:
    """Rename a save's or state's file, taking its thumbnail along.

    Args:
        siblings: The ROM's other assets of the same kind. Uploads find the one
            to update by name, so the new name must be free among them.

    Returns:
        The name columns to write onto the asset's row, none when unchanged.
    """
    try:
        new_name = sanitize_filename(file_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid filename: {exc}",
        ) from exc
    if new_name == asset.file_name:
        return {}
    # The thumbnail follows the stem, so a bare extension would strand it.
    new_stem = compute_file_name_no_ext(new_name)
    if not new_stem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: it needs a name before the extension",
        )

    folded = new_name.casefold()
    if any(
        other.id != asset.id and other.file_name.casefold() == folded
        for other in siblings
    ):
        raise _name_taken(new_name)

    # Thumbnails bind by stem, so taking a stem another screenshot holds would
    # show that one, and delete it along with the asset.
    thumbnail = asset.screenshot
    bound = db_screenshot_handler.get_screenshot(
        rom_id=asset.rom_id,
        user_id=asset.user_id,
        file_name=new_name,
        file_name_no_ext=new_stem,
    )
    if bound and (thumbnail is None or bound.id != thumbnail.id):
        raise _name_taken(bound.file_name)

    # A gallery screenshot sharing the stem is bound by chance, so it stays put.
    if thumbnail and thumbnail.is_gallery:
        thumbnail = None
    thumbnail_name = (
        f"{new_stem}{os.path.splitext(thumbnail.file_name)[1]}" if thumbnail else ""
    )

    log.info(f"Renaming {hl(asset.file_name)} to {hl(new_name)}")
    try:
        await _move_asset_files(asset, new_name, thumbnail, thumbnail_name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{asset.file_name} not found on disk",
        ) from exc
    except FileExistsError as exc:
        raise _name_taken(new_name) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
        ) from exc

    if thumbnail:
        db_screenshot_handler.update_screenshot(
            thumbnail.id, _file_name_columns(thumbnail_name)
        )
    return _file_name_columns(new_name)
