"""Filing a state or screenshot: write the bytes, scan them, upsert the row.

Shared by the upload routes and the streaming sync. What differs between them
(dedup, retention, where the bytes came from) stays with the caller. So does
renaming a save or state, which takes its thumbnail along.
"""

import os
from collections.abc import Sequence
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, TypeAlias, cast

from fastapi import HTTPException, UploadFile, status

from handler.database import (
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_screenshot, scan_state
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.base import compute_file_name_no_ext
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


async def release_thumbnail(screenshot: Screenshot | None) -> None:
    """Drop a deleted save's or state's thumbnail, unless something still shows it."""
    # A gallery screenshot sharing the stem is bound by chance, so it stays put.
    if not screenshot or screenshot.is_gallery:
        return
    # A save and a state of one stem share a thumbnail; the other keeps it.
    if db_screenshot_handler.is_bound(screenshot):
        return
    db_screenshot_handler.delete_screenshot(screenshot.id)
    path = f"{screenshot.file_path}/{screenshot.file_name}"
    # A filesystem that ignores case holds another row's spelling as this file.
    if any(
        fs_asset_handler.is_same_file(path, f"{variant.file_path}/{variant.file_name}")
        for variant in db_screenshot_handler.get_name_variants(screenshot)
    ):
        return
    await remove_asset_file(path, "Screenshot file")


async def unrecorded_hash(save: Save) -> str | None:
    """The file's hash for a slotted save never hashed, so its removal is still recorded."""
    if save.slot and not save.content_hash:
        return await fs_asset_handler.compute_content_hash(save.full_path)
    return None


async def remove_save(save: Save) -> None:
    """Drop a save row with its file and screenshot."""
    db_save_handler.delete_save(save.id, content_hash=await unrecorded_hash(save))
    await remove_asset_file(save.full_path, "Save file")
    await release_thumbnail(save.screenshot)


async def prune_save_slot(user_id: int, rom_id: int, slot: str, keep: int) -> None:
    """Drop every version of ``slot`` past the ``keep`` newest, files included."""
    # Hashed before the prune, so a version never hashed is recorded along with it.
    fallback_hashes = {}
    for version in db_save_handler.get_unhashed_versions_past(
        user_id, rom_id, slot, keep
    ):
        content_hash = await fs_asset_handler.compute_content_hash(
            f"{version.file_path}/{version.file_name}"
        )
        if content_hash:
            fallback_hashes[version.id] = content_hash
    pruned = db_save_handler.prune_slot(
        user_id=user_id,
        rom_id=rom_id,
        slot=slot,
        keep=keep,
        fallback_hashes=fallback_hashes,
    )
    for version in pruned:
        await remove_asset_file(f"{version.file_path}/{version.file_name}", "Save file")
        await release_thumbnail(
            db_screenshot_handler.get_screenshot(
                rom_id=rom_id,
                user_id=user_id,
                file_name=version.file_name,
                file_name_no_ext=version.file_name_no_ext,
            )
        )


def _name_taken(file_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"{file_name} already exists",
    )


def _is_same(a: Save | State, b: Save | State) -> bool:
    return type(a) is type(b) and a.id == b.id


async def _move_asset_files(
    asset: Save | State,
    new_name: str,
    thumbnail: Screenshot | None,
    thumbnail_name: str,
    copy_thumbnail: bool,
) -> None:
    """Rename an asset's file, then move or copy its thumbnail's, undoing the
    first if the second fails."""
    await fs_asset_handler.rename_file(asset.full_path, new_name)
    if thumbnail is None:
        return
    source = f"{thumbnail.file_path}/{thumbnail.file_name}"
    try:
        if copy_thumbnail:
            await fs_asset_handler.copy_to_new_file(
                source, f"{thumbnail.file_path}/{thumbnail_name}"
            )
        else:
            await fs_asset_handler.rename_file(source, thumbnail_name)
    except FileNotFoundError:
        # Only the row is left to rename, so the asset stays bound to it.
        pass
    except Exception:
        await fs_asset_handler.rename_file(
            f"{asset.file_path}/{new_name}", asset.file_name
        )
        raise


async def _restore_asset_files(
    asset: Save | State,
    new_name: str,
    thumbnail: Screenshot | None,
    thumbnail_name: str,
    copy_thumbnail: bool,
) -> None:
    """Put the files back under the names their unchanged rows still carry."""
    await fs_asset_handler.rename_file(f"{asset.file_path}/{new_name}", asset.file_name)
    if thumbnail is None:
        return
    placed = f"{thumbnail.file_path}/{thumbnail_name}"
    try:
        if copy_thumbnail:
            await fs_asset_handler.remove_file(placed)
        else:
            await fs_asset_handler.rename_file(placed, thumbnail.file_name)
    except FileNotFoundError:
        pass


async def rename_asset[AssetT: (Save, State)](asset: AssetT, file_name: str) -> AssetT:
    """Rename a save's or state's file and row, taking its thumbnail along."""
    try:
        new_name = sanitize_filename(file_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid filename: {exc}",
        ) from exc
    if new_name == asset.file_name:
        return asset
    # The thumbnail follows the stem, so a bare extension would strand it.
    new_stem = compute_file_name_no_ext(new_name)
    if not new_stem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: it needs a name before the extension",
        )

    saves: Sequence[Save] = db_save_handler.get_saves(
        user_id=asset.user_id, rom_ids=[asset.rom_id]
    )
    states: Sequence[State] = db_state_handler.get_states(
        user_id=asset.user_id, rom_ids=[asset.rom_id]
    )
    everything: list[Save | State] = [*saves, *states]
    others = [a for a in everything if not _is_same(a, asset)]
    # Uploads find the one to update by name, so it must be free among its kind.
    folded = new_name.casefold()
    if any(
        type(other) is type(asset) and other.file_name.casefold() == folded
        for other in others
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
    # A save and a state of one stem share a thumbnail; the other keeps it.
    copy_thumbnail = thumbnail is not None and db_screenshot_handler.is_bound(
        thumbnail, ignoring=asset
    )
    # The new name still resolves the shared one, by stem or through a
    # collation that ignores case.
    if thumbnail and copy_thumbnail and bound:
        thumbnail = None
    # A filesystem that ignores case already answers to the copy's name, so
    # only its row is new.
    thumbnail_file = thumbnail
    if (
        thumbnail
        and copy_thumbnail
        and fs_asset_handler.is_same_file(
            f"{thumbnail.file_path}/{thumbnail.file_name}",
            f"{thumbnail.file_path}/{thumbnail_name}",
        )
    ):
        thumbnail_file = None

    log.info(f"Renaming {hl(asset.file_name)} to {hl(new_name)}")
    moves = (asset, new_name, thumbnail_file, thumbnail_name, copy_thumbnail)
    try:
        await _move_asset_files(*moves)
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

    try:
        with sync_session.begin() as session:
            if thumbnail and copy_thumbnail:
                db_screenshot_handler.add_screenshot(
                    Screenshot(
                        rom_id=asset.rom_id,
                        user_id=asset.user_id,
                        file_name=thumbnail_name,
                        file_path=thumbnail.file_path,
                        file_size_bytes=thumbnail.file_size_bytes,
                        is_public=asset.is_public,
                    ),
                    session=session,
                )
            elif thumbnail:
                db_screenshot_handler.update_screenshot(
                    thumbnail.id, {"file_name": thumbnail_name}, session=session
                )
            if isinstance(asset, Save):
                # Redundant only in mypy's AssetT=Save pass; the State pass needs it.
                return cast(  # type: ignore[redundant-cast]
                    AssetT,
                    db_save_handler.update_save(
                        asset.id, {"file_name": new_name}, touch=False, session=session
                    ),
                )
            return db_state_handler.update_state(
                asset.id, {"file_name": new_name}, touch=False, session=session
            )
    except Exception:
        await _restore_asset_files(*moves)
        raise
