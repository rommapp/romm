import asyncio
import io
import os
import zipfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Final
from urllib.parse import quote

from fastapi import (
    Body,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from adapters.services.sigil import (
    NATIVE_SAVE_PLATFORM_SLUGS,
    SIGIL_RESTORE_PLATFORM_SLUGS,
    SigilGame,
    SigilService,
)
from adapters.services.sigil_restore import (
    ContainerMismatch,
    RefusalCode,
    RestoreCompanion,
    RestoredSave,
    RestoreTarget,
    SaveRestoreError,
    SharedContainerRequired,
    SigilRefusal,
    merge_into_container,
    restore_layouts,
    restore_per_game,
)
from config import MAX_AUTOCLEANUP_LIMIT, MAX_SAVES_PER_SLOT
from decorators.auth import protected_route
from endpoints.responses.assets import (
    SaveLayoutSchema,
    SaveSchema,
    SaveSummarySchema,
    SlotSummarySchema,
)
from endpoints.responses.device import DeviceSyncSchema
from endpoints.roms import refresh_affected_smart_collections
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.asset_store import (
    assert_backup,
    prune_save_slot,
    remove_save,
    rename_asset,
    store_screenshot,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_snapshot_handler,
    db_sync_session_handler,
)
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import check_upload_archive, leaves_save_folder
from handler.scan_handler import scan_save
from handler.snapshots.bridge import hold_legacy_upload
from handler.snapshots.legacy import sync_file
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import (
    EMULATOR_MAX_LENGTH,
    EMULATOR_VERSION_MAX_LENGTH,
    SAVE_SLOT_MAX_LENGTH,
    Save,
)
from models.base import FILE_NAME_MAX_LENGTH, FILE_PATH_MAX_LENGTH
from models.device import Device
from models.device_save_sync import DeviceSaveSync
from models.rom import Rom, RomFile
from utils.assets import normalize_asset_labels
from utils.datetime import to_utc
from utils.memory_cards import MEMORY_CARD_MAX_BYTES
from utils.nginx import content_disposition
from utils.router import APIRouter
from utils.uploads import (
    apply_datetime_tag,
    check_asset_upload_size,
    check_emulator_folder_name,
    sanitize_asset_filename,
)
from utils.validation import RomIdScope, narrow_rom_id_scope
from utils.zip_cache import ensure_zipfile_writable


def _build_save_schema(
    save: Save,
    syncs: Sequence[tuple[DeviceSaveSync, str | None]] = (),
    device: Device | None = None,
) -> SaveSchema:
    """Attach one ``DeviceSyncSchema`` per device that has synced this save.

    ``syncs`` is the full list of sync rows (paired with device name) for this
    save across every device, so clients can attribute the save to its creator.
    ``device`` is the caller's device, when supplied: its entry is emitted first
    for stable ordering and old-client compatibility, and a placeholder entry is
    synthesized when the caller has not yet synced this save.
    """
    save_schema = SaveSchema.model_validate(save)

    save_updated = to_utc(save.updated_at)
    caller_present = False
    entries: list[DeviceSyncSchema] = []
    for sync, device_name in syncs:
        if device and sync.device_id == device.id:
            caller_present = True
        entries.append(
            DeviceSyncSchema(
                device_id=sync.device_id,
                device_name=device_name,
                last_synced_at=sync.last_synced_at,
                is_untracked=sync.is_untracked,
                is_current=to_utc(sync.last_synced_at) >= save_updated,
            )
        )

    if device and not caller_present:
        entries.append(
            DeviceSyncSchema(
                device_id=device.id,
                device_name=device.name,
                last_synced_at=save.updated_at,
                is_untracked=False,
                is_current=False,
            )
        )

    if device:
        entries.sort(key=lambda entry: entry.device_id != device.id)

    save_schema.device_syncs = entries
    return save_schema


def _syncs_for_save(
    save_id: int, device: Device | None
) -> list[tuple[DeviceSaveSync, str | None]]:
    """Fetch every device sync for a single save when a device is in context.

    Device attribution is only meaningful to a device-scoped caller, so callers
    without a device get an empty list and no query is issued.
    """
    if not device:
        return []
    return db_device_save_sync_handler.get_syncs_for_saves([save_id]).get(save_id, [])


def _slot_retention(autocleanup: bool, autocleanup_limit: int) -> int | None:
    """Versions to keep in a slot: the tighter of the client's ask and the server cap."""
    limits = [MAX_SAVES_PER_SLOT] if MAX_SAVES_PER_SLOT else []
    if autocleanup:
        limits.append(autocleanup_limit)
    return min(limits, default=None)


def _resolve_device(
    device_id: str | None,
    user_id: int,
    scopes: set[str] | None = None,
    required_scope: Scope | None = None,
) -> Device | None:
    if not device_id:
        return None

    if required_scope and scopes and required_scope not in scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = db_device_handler.get_device(device_id=device_id, user_id=user_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return device


def _record_device_sync(
    device_id: str, save: Save, user_id: int, client_hash: str | None = None
) -> None:
    """Mark the device as synced to the save's current version."""
    db_device_save_sync_handler.upsert_sync(
        device_id=device_id,
        save_id=save.id,
        synced_at=save.updated_at,
        last_sync_hash=client_hash,
        last_sync_server_hash=save.content_hash,
    )
    db_device_handler.update_last_seen(device_id=device_id, user_id=user_id)


def _increment_session_counter(session_id: int, user_id: int) -> None:
    try:
        db_sync_session_handler.increment_operations_completed(
            session_id=session_id,
            user_id=user_id,
        )
    except Exception:
        log.warning(f"Failed to update sync session {session_id}", exc_info=True)


def _owned_save_or_404(id: int, user_id: int) -> Save:
    save = db_save_handler.get_save(user_id=user_id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )
    return save


router = APIRouter(
    prefix="/saves",
    tags=["saves"],
)

SAVE_FILE_UPLOAD = File(..., description="Save file to upload.")
SAVE_SCREENSHOT_UPLOAD = File(
    default=None,
    description="Screenshot file associated with this save.",
)
SAVE_FILE_UPDATE = File(default=None, description="Updated save file content.")
# A converted save's path relative to the emulator's save root, percent-encoded.
SAVE_PATH_HEADER: Final = "X-Save-Path"
SAVE_SCREENSHOT_UPDATE = File(default=None, description="Updated screenshot file.")


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_save(
    request: Request,
    rom_id: int,
    emulator: Annotated[str | None, Query(max_length=EMULATOR_MAX_LENGTH)] = None,
    emulator_version: Annotated[
        str | None, Query(max_length=EMULATOR_VERSION_MAX_LENGTH)
    ] = None,
    core: Annotated[
        str | None,
        Query(
            max_length=EMULATOR_MAX_LENGTH,
            description="The libretro core that wrote the save, when one did.",
        ),
    ] = None,
    core_version: Annotated[
        str | None, Query(max_length=EMULATOR_VERSION_MAX_LENGTH)
    ] = None,
    slot: Annotated[str | None, Query(max_length=SAVE_SLOT_MAX_LENGTH)] = None,
    device_id: str | None = None,
    # Over-long hashes are stored as unknown by upsert_sync.
    content_hash: Annotated[str | None, Query()] = None,
    session_id: int | None = None,
    overwrite: bool = False,
    autocleanup: bool = False,
    autocleanup_limit: int = 10,
    saveFile: UploadFile = SAVE_FILE_UPLOAD,
    screenshotFile: UploadFile | None = SAVE_SCREENSHOT_UPLOAD,
) -> SaveSchema:
    """Upload a save file for a ROM."""
    check_asset_upload_size(saveFile, "Save file")
    check_asset_upload_size(screenshotFile, "Screenshot file")
    check_upload_archive(saveFile, "Save file")

    # Keep at least the save just uploaded, and cap what a client can retain
    autocleanup_limit = max(1, min(autocleanup_limit, MAX_AUTOCLEANUP_LIMIT))
    keep = _slot_retention(autocleanup, autocleanup_limit)

    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_WRITE
    )

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    assert_rom_visible(request, rom)

    if not saveFile.filename:
        log.error("Save file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Save file has no filename"
        )

    actual_filename = sanitize_asset_filename(saveFile.filename, "save")
    if slot:
        # Checked again because the tag adds 26 bytes.
        actual_filename = sanitize_asset_filename(
            apply_datetime_tag(actual_filename), "save"
        )

    sanitized_screenshot_filename = ""
    if screenshotFile and screenshotFile.filename:
        sanitized_screenshot_filename = sanitize_asset_filename(
            screenshotFile.filename, "screenshot"
        )
        # Save.screenshot is matched by stem, so a slotted upload names the
        # screenshot after the tagged save whatever the client called it.
        if slot:
            save_stem, _ = os.path.splitext(actual_filename)
            _, screenshot_ext = os.path.splitext(sanitized_screenshot_filename)
            sanitized_screenshot_filename = sanitize_asset_filename(
                f"{save_stem}{screenshot_ext}", "screenshot"
            )

    check_emulator_folder_name(emulator)

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    db_save = db_save_handler.get_save_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=actual_filename, slot=slot
    )

    if device and slot and not overwrite:
        slot_saves = db_save_handler.get_saves(
            user_id=request.user.id,
            rom_ids=[rom.id],
            slot=slot,
            order_by="updated_at",
        )
        latest_in_slot = db_snapshot_handler.current_saves_for_slots(
            request.user.id, {(rom.id, slot)}, [emulator], [core]
        ).get((rom.id, slot)) or (slot_saves[0] if slot_saves else None)
        if latest_in_slot:
            sync = db_device_save_sync_handler.get_sync(
                device_id=device.id, save_id=latest_in_slot.id
            )
            if not sync or to_utc(sync.last_synced_at) < to_utc(
                latest_in_slot.updated_at
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Slot has a newer save since your last sync",
                )
    elif device and db_save and not overwrite:
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=db_save.id
        )
        if sync and to_utc(sync.last_synced_at) < to_utc(db_save.updated_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Save has been updated since your last sync",
            )

    log.info(
        f"Uploading save {hl(actual_filename)} for {hl(str(rom.name), color=BLUE)}"
    )

    # Looked up before the write, which replaces a colliding save's bytes.
    colliding_save = (
        None
        if db_save
        else db_save_handler.get_save_by_path(
            user_id=request.user.id,
            rom_id=rom.id,
            file_path=saves_path,
            file_name=actual_filename,
        )
    )
    replaced = db_save or colliding_save
    if replaced:
        assert_backup(replaced)
    replaced_hash = (
        await fs_asset_handler.unrecorded_hash(replaced) if replaced else None
    )
    await fs_asset_handler.write_file(
        file=saveFile, path=saves_path, filename=actual_filename
    )

    scanned_save = await scan_save(
        file_name=actual_filename,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )

    if slot and scanned_save.content_hash and not overwrite:
        existing_by_hash = db_save_handler.get_save_by_content_hash(
            user_id=request.user.id,
            rom_id=rom.id,
            content_hash=scanned_save.content_hash,
            slot=slot,
        )
        if existing_by_hash:
            try:
                await fs_asset_handler.remove_file(f"{saves_path}/{actual_filename}")
            except FileNotFoundError:
                pass
            # A retry still counts as an upload to the slot, so the cap applies.
            if keep is not None:
                await prune_save_slot(request.user.id, rom.id, slot, keep)
            # Pruning can drop the matched version when it is not among the newest.
            if device and db_save_handler.get_save(
                user_id=request.user.id, id=existing_by_hash.id
            ):
                _record_device_sync(
                    device.id, existing_by_hash, request.user.id, content_hash
                )
            return _build_save_schema(
                existing_by_hash, _syncs_for_save(existing_by_hash.id, device), device
            )

    # Refresh hash if the file already exists to avoid mismatched metadata.
    if colliding_save and colliding_save.content_hash != scanned_save.content_hash:
        db_save = colliding_save

    if db_save:
        # Track file path and emulator to prevent hash-content drift.
        stale_full_path = db_save.full_path
        update_data: dict[str, Any] = {
            "file_size_bytes": scanned_save.file_size_bytes,
            "content_hash": scanned_save.content_hash,
            "file_path": scanned_save.file_path,
            "emulator": emulator,
        }
        reported = {
            "emulator_version": emulator_version,
            "core": core,
            "core_version": core_version,
        }
        update_data |= {k: v for k, v in reported.items() if v is not None}
        if slot is not None:
            update_data["slot"] = slot
        db_save = db_save_handler.update_save(
            db_save.id, update_data, replaced_hash=replaced_hash
        )

        # Delete orphaned bytes only if no other row references the old path.
        if stale_full_path != db_save.full_path:
            still_referenced = any(
                other.id != db_save.id and other.full_path == stale_full_path
                for other in db_save_handler.get_saves(
                    user_id=request.user.id, rom_ids=[rom.id]
                )
            )
            if not still_referenced:
                try:
                    await fs_asset_handler.remove_file(stale_full_path)
                except FileNotFoundError:
                    pass
    else:
        scanned_save.rom_id = rom.id
        scanned_save.user_id = request.user.id
        scanned_save.emulator = emulator
        scanned_save.emulator_version = emulator_version
        scanned_save.core = core
        scanned_save.core_version = core_version
        scanned_save.slot = slot
        scanned_save.origin_device_id = device.id if device else None
        db_save = db_save_handler.add_save(save=scanned_save)

    if device:
        _record_device_sync(device.id, db_save, request.user.id, content_hash)

    if session_id:
        _increment_session_counter(session_id, request.user.id)

    if screenshotFile and sanitized_screenshot_filename:
        await store_screenshot(
            request.user,
            rom,
            screenshotFile,
            sanitized_screenshot_filename,
            is_public=db_save.is_public,
        )

    # After the screenshot, so the snapshot it may write can show it.
    if slot:
        await hold_legacy_upload(
            db_save, request.user, rom, device.id if device else None
        )
        db_save = db_save_handler.get_save(user_id=request.user.id, id=db_save.id)
        assert db_save is not None

    # Last, so a version the bridge just made a snapshot hold is never pruned.
    if slot and keep is not None:
        await prune_save_slot(request.user.id, rom.id, slot, keep)

    rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    refresh_affected_smart_collections([rom.id], membership_only=True)

    return _build_save_schema(db_save, _syncs_for_save(db_save.id, device), device)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_saves(
    request: Request,
    rom_id: int | None = None,
    rom_ids: Annotated[
        RomIdScope,
        Query(
            description=(
                "ROM IDs to scope the results to, for clients syncing a known "
                "set of ROMs. Multiple values are allowed by repeating the "
                "parameter. Combined with `rom_id` when both are given."
            ),
        ),
    ] = None,
    platform_id: int | None = None,
    device_id: str | None = None,
    slot: str | None = None,
) -> list[SaveSchema]:
    """Retrieve saves for the current user."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    saves = db_save_handler.get_saves(
        user_id=request.user.id,
        rom_ids=narrow_rom_id_scope(rom_id, rom_ids),
        platform_id=platform_id,
        slot=slot,
    )

    if not device:
        return [_build_save_schema(save) for save in saves]

    syncs_by_save_id = db_device_save_sync_handler.get_syncs_for_saves(
        [s.id for s in saves]
    )

    return [
        _build_save_schema(save, syncs_by_save_id.get(save.id, []), device)
        for save in saves
    ]


@protected_route(router.get, "/identifiers", [Scope.ASSETS_READ])
def get_save_identifiers(request: Request) -> list[int]:
    """Retrieve save identifiers."""
    return db_save_handler.get_save_ids(user_id=request.user.id)


@protected_route(router.get, "/summary", [Scope.ASSETS_READ])
def get_saves_summary(request: Request, rom_id: int) -> SaveSummarySchema:
    """Retrieve saves summary grouped by slot."""
    summary_data = db_save_handler.get_saves_summary(
        user_id=request.user.id, rom_id=rom_id
    )

    slots = [
        SlotSummarySchema(
            slot=slot_data["slot"],
            count=slot_data["count"],
            latest=_build_save_schema(slot_data["latest"]),
        )
        for slot_data in summary_data["slots"]
    ]

    return SaveSummarySchema(total_count=summary_data["total_count"], slots=slots)


@protected_route(
    router.get,
    "/layouts",
    [Scope.ASSETS_READ],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_503_SERVICE_UNAVAILABLE: {},
    },
)
def get_save_layouts(
    request: Request,
    platform: Annotated[str, Query(description="A RomM platform slug.")],
) -> list[SaveLayoutSchema]:
    """List the layouts a save converts to for a platform, as the content route's `core`.

    The libretro default row comes first, then each row for the platform and
    each row that applies to any platform.
    """
    sigil_platform = _sigil_platform_or_400(platform)
    if not SigilService.is_enabled():
        raise _sigil_missing()
    return [
        SaveLayoutSchema.model_validate(row) for row in restore_layouts(sigil_platform)
    ]


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_save(request: Request, id: int, device_id: str | None = None) -> SaveSchema:
    """Retrieve a save by ID."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


def _readable_save_or_404(request: Request, id: int) -> Save:
    """The save, when the caller owns it or it is public and its ROM is visible."""
    save = db_save_handler.get_save_by_id(id)
    if not save or (save.user_id != request.user.id and not save.is_public):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    # Sharing must not override the hidden-ROM/platform policy: a save on a ROM
    # hidden from the caller stays 404-masked, just like the ROM itself.
    if save.rom is not None:
        assert_rom_visible(
            request, save.rom, not_found_detail=f"Save with ID {id} not found"
        )
    return save


def _stored_save_path(save: Save) -> Path:
    try:
        file_path = fs_asset_handler.validate_path(save.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save file not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save file not found on disk",
        )
    return file_path


def _record_download(
    request: Request,
    save: Save,
    device: Device | None,
    session_id: int | None,
    optimistic: bool,
) -> None:
    # Sync bookkeeping only makes sense for the owner's own saves.
    if device and optimistic and save.user_id == request.user.id:
        # The device has no bytes yet, so only the server half is known.
        _record_device_sync(device.id, save, request.user.id)

    if session_id:
        _increment_session_counter(session_id, request.user.id)


def _parse_options(option: Sequence[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in option:
        key, separator, value = item.partition(":")
        if not separator or not key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Option {item!r} isn't in the form key:value",
            )
        options[key] = value
    return options


def _content_path(save: Save, rom: Rom, rom_files: Sequence[RomFile]) -> str:
    """The ROM file name a restore names files after: the save's channel file,
    else the file the ROM's channels key to."""
    channel = (
        db_snapshot_handler.get_channel(save.channel_id) if save.channel_id else None
    )
    rom_file = (
        db_snapshot_handler.get_channel_file(channel) if channel else None
    ) or sync_file(rom_files)
    return rom_file.file_name if rom_file else rom.fs_name


def _sigil_platform_or_400(platform_slug: str) -> str:
    sigil_platform = SIGIL_RESTORE_PLATFORM_SLUGS.get(platform_slug)
    if sigil_platform is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saves for {platform_slug} can't be converted for a core",
        )
    return sigil_platform


def _sigil_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Save conversion needs sigil, which this server lacks",
    )


def _stored_game_or_error(rom: Rom) -> tuple[SigilGame, list[RomFile]]:
    _sigil_platform_or_400(rom.platform_slug)
    rom_files = db_rom_handler.rom_files_for_rom_id(rom.id)
    game = SigilService.stored_game(rom, rom_files)
    if game is None:
        raise _sigil_missing()
    return game, rom_files


async def _companions(
    request: Request, companion_ids: Sequence[int]
) -> list[RestoreCompanion]:
    """Each companion save's game and unit, under the same read rules as a download."""
    companions: list[RestoreCompanion] = []
    for companion_id in companion_ids:
        save = _readable_save_or_404(request, companion_id)
        path = _stored_save_path(save)
        if save.rom is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Companion save {companion_id} has no ROM",
            )
        game, _ = _stored_game_or_error(save.rom)
        companions.append(
            RestoreCompanion(
                game_ids=game.game_ids, unit=await asyncio.to_thread(path.read_bytes)
            )
        )
    return companions


_REFUSAL_STATUS: Final[dict[RefusalCode, int]] = {
    RefusalCode.CONFLICT: status.HTTP_409_CONFLICT,
    RefusalCode.UNCOLLECTED: status.HTTP_409_CONFLICT,
    RefusalCode.EXISTS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.DAMAGED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.REGION: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.NO_SPACE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.NOT_FOUND: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.UNSUPPORTED_FORMAT: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RefusalCode.NO_TARGET: status.HTTP_400_BAD_REQUEST,
    RefusalCode.AMBIGUOUS: status.HTTP_400_BAD_REQUEST,
    RefusalCode.INVALID_ARG: status.HTTP_400_BAD_REQUEST,
    RefusalCode.IO: status.HTTP_500_INTERNAL_SERVER_ERROR,
    RefusalCode.OTHER: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _restore_error(exc: SaveRestoreError) -> HTTPException:
    if isinstance(exc, SigilRefusal):
        return HTTPException(
            status_code=_REFUSAL_STATUS[exc.code],
            detail={
                "error": exc.code.value,
                "message": str(exc),
                "problem": exc.problem,
                "profiles": [
                    {"id": profile.id, "name": profile.name} for profile in exc.profiles
                ],
            },
        )
    if isinstance(exc, SharedContainerRequired):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "SHARED_CONTAINER",
                "message": str(exc),
                "container_path": exc.container_path,
            },
        )
    if isinstance(exc, ContainerMismatch):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "CONTAINER_MISMATCH",
                "message": str(exc),
                "container_path": exc.container_path,
                "written": list(exc.written),
                "options": exc.options,
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
    )


def _restored_response(restored: RestoredSave, save: Save) -> Response:
    """One file raw, named by `X-Save-Path`; several as a zip of save-root paths."""
    if len(restored.files) == 1:
        ((path, data),) = restored.files.items()
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": content_disposition(PurePosixPath(path).name),
                SAVE_PATH_HEADER: quote(path),
            },
        )
    # `zipfile_inflate64`, imported for ROM archives, breaks `writestr()` until this runs.
    ensure_zipfile_writable()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in sorted(restored.files.items()):
            zf.writestr(path, data)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": content_disposition(
                f"{PurePosixPath(save.file_name).stem}.zip"
            )
        },
    )


_DOWNLOAD_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    status.HTTP_400_BAD_REQUEST: {},
    status.HTTP_404_NOT_FOUND: {},
    status.HTTP_409_CONFLICT: {},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {},
    status.HTTP_503_SERVICE_UNAVAILABLE: {},
}


@protected_route(
    router.get,
    "/{id}/content",
    [Scope.ASSETS_READ],
    responses=_DOWNLOAD_RESPONSES,
)
async def download_save(
    request: Request,
    id: int,
    device_id: str | None = None,
    session_id: int | None = None,
    optimistic: bool = True,
    core: Annotated[
        str | None,
        Query(
            max_length=EMULATOR_MAX_LENGTH,
            description=(
                "A sigil layout id (libretro core name or emulator id). The save "
                "comes back as the files that emulator reads, for a per-game target."
            ),
        ),
    ] = None,
    option: Annotated[
        list[str] | None,
        Query(
            description="An emulator option that changes the save's shape, as key:value. Repeatable."
        ),
    ] = None,
    profile: Annotated[
        str | None, Query(description="The user profile whose account save to write.")
    ] = None,
    companion: Annotated[
        list[int] | None,
        Query(description="A save whose game this game reads saves of. Repeatable."),
    ] = None,
) -> Response:
    """Download a save file.

    With `core`, the save is restored as that emulator reads it. One file comes
    back raw with its save-root-relative path, percent-encoded, in `X-Save-Path`;
    several come back as a zip of save-root-relative paths. A target that is a
    card or volume every game shares is refused with the `container_path` to
    POST instead.
    """
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )
    save = _readable_save_or_404(request, id)
    file_path = _stored_save_path(save)

    response: Response
    rom = save.rom
    if core is None or (rom and rom.platform_slug in NATIVE_SAVE_PLATFORM_SLUGS):
        response = FileResponse(path=str(file_path), filename=save.file_name)
    else:
        if rom is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Save {id} has no ROM to convert it for",
            )
        options = _parse_options(option or [])
        game, rom_files = _stored_game_or_error(rom)
        companions = await _companions(request, companion or [])
        target = RestoreTarget(
            core=core,
            options=options,
            profile=profile,
            content_path=_content_path(save, rom, rom_files),
        )
        unit = await asyncio.to_thread(file_path.read_bytes)
        try:
            restored = await restore_per_game(unit, game, target, companions)
        except SaveRestoreError as exc:
            raise _restore_error(exc) from exc
        response = _restored_response(restored, save)

    _record_download(request, save, device, session_id, optimistic)
    return response


class SaveConversionPayload(BaseModel):
    """What a client's emulator reads, and where its container sits."""

    core: str = Field(max_length=EMULATOR_MAX_LENGTH)
    options: dict[str, str] = Field(default_factory=dict)
    profile: str | None = None
    container_path: str = Field(max_length=FILE_PATH_MAX_LENGTH)
    companions: list[int] = Field(default_factory=list)


@protected_route(
    router.post,
    "/{id}/content",
    [Scope.ASSETS_READ],
    responses={
        **_DOWNLOAD_RESPONSES,
        status.HTTP_413_CONTENT_TOO_LARGE: {},
    },
)
async def merge_save_into_container(
    request: Request,
    id: int,
    payload: Annotated[
        str,
        Form(
            alias="request",
            description=(
                "JSON: core, options, profile, container_path (relative to the "
                "save root) and companions (save ids)."
            ),
        ),
    ],
    container: Annotated[
        UploadFile,
        File(description="The client's current card or volume at container_path."),
    ],
    device_id: str | None = None,
    session_id: int | None = None,
    optimistic: bool = True,
) -> Response:
    """Merge a save into the card or volume the client sent, and return it.

    Only the save's game's saves change; every other game's stay. The response
    names the container in `X-Save-Path`. A restore that would write any other
    file is refused, naming the option that selects the sent container.
    """
    try:
        conversion = SaveConversionPayload.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc
    container_path = conversion.container_path
    if not container_path or leaves_save_folder(container_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"container_path {container_path!r} leaves the save root",
        )
    content = await container.read(MEMORY_CARD_MAX_BYTES + 1)
    if len(content) > MEMORY_CARD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The container exceeds {MEMORY_CARD_MAX_BYTES} bytes",
        )

    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )
    save = _readable_save_or_404(request, id)
    file_path = _stored_save_path(save)
    rom = save.rom
    if rom is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Save {id} has no ROM to convert it for",
        )
    if rom.platform_slug in NATIVE_SAVE_PLATFORM_SLUGS:
        _record_download(request, save, device, session_id, optimistic)
        return FileResponse(path=str(file_path), filename=save.file_name)
    game, rom_files = _stored_game_or_error(rom)
    companions = await _companions(request, conversion.companions)
    target = RestoreTarget(
        core=conversion.core,
        options=conversion.options,
        profile=conversion.profile,
        content_path=_content_path(save, rom, rom_files),
    )
    unit = await asyncio.to_thread(file_path.read_bytes)
    try:
        restored = await merge_into_container(
            unit, game, target, container_path, content, companions
        )
    except SaveRestoreError as exc:
        raise _restore_error(exc) from exc

    _record_download(request, save, device, session_id, optimistic)
    return _restored_response(restored, save)


@protected_route(router.post, "/{id}/downloaded", [Scope.DEVICES_WRITE])
def confirm_download(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
    content_hash: str | None = Body(default=None, embed=True),
) -> SaveSchema:
    """Confirm a save was downloaded successfully."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    synced_at, server_hash = save.updated_at, save.content_hash
    served = db_device_save_sync_handler.get_sync(device_id=device_id, save_id=save.id)
    if served and served.last_sync_server_hash and not served.last_sync_hash:
        # The download recorded the version it served; the server may have moved since.
        synced_at, server_hash = served.last_synced_at, served.last_sync_server_hash
    elif content_hash != server_hash:
        # Without the served version, only a hash equal to the server's proves what the device holds.
        content_hash = server_hash = None
    db_device_save_sync_handler.upsert_sync(
        device_id=device_id,
        save_id=save.id,
        synced_at=synced_at,
        last_sync_hash=content_hash,
        last_sync_server_hash=server_hash,
    )
    db_device_handler.update_last_seen(device_id=device_id, user_id=request.user.id)

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_save(
    request: Request,
    id: int,
    device_id: str | None = None,
    content_hash: Annotated[str | None, Query()] = None,
    saveFile: UploadFile | None = SAVE_FILE_UPDATE,
    screenshotFile: UploadFile | None = SAVE_SCREENSHOT_UPDATE,
) -> SaveSchema:
    """Update a save file."""

    check_asset_upload_size(saveFile, "Save file")
    check_asset_upload_size(screenshotFile, "Screenshot file")
    check_upload_archive(saveFile, "Save file")

    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_WRITE
    )

    db_save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not db_save:
        error = f"Save with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    sanitized_screenshot_filename = (
        sanitize_asset_filename(screenshotFile.filename, "screenshot")
        if screenshotFile and screenshotFile.filename
        else ""
    )

    rom = db_save.attached_rom
    if saveFile:
        assert_backup(db_save)
        replaced_hash = await fs_asset_handler.unrecorded_hash(db_save)
        await fs_asset_handler.write_file(
            file=saveFile, path=db_save.file_path, filename=db_save.file_name
        )
        scanned_save = await scan_save(
            file_name=db_save.file_name,
            user=request.user,
            platform_fs_slug=rom.platform_fs_slug,
            rom_id=rom.id,
            emulator=db_save.emulator,
        )
        db_save = db_save_handler.update_save(
            db_save.id,
            {
                "file_size_bytes": scanned_save.file_size_bytes,
                "content_hash": scanned_save.content_hash,
            },
            replaced_hash=replaced_hash,
        )

    if screenshotFile and sanitized_screenshot_filename:
        await store_screenshot(
            request.user,
            rom,
            screenshotFile,
            sanitized_screenshot_filename,
            is_public=db_save.is_public,
        )

    # Set the last played time for the current user
    rom_user = db_rom_handler.get_rom_user(rom.id, request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(rom.id, request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    if device:
        # A client hash is only a baseline when the save bytes came with it.
        client_hash = content_hash if saveFile else None
        _record_device_sync(device.id, db_save, request.user.id, client_hash)

    return _build_save_schema(db_save, _syncs_for_save(db_save.id, device), device)


@protected_route(
    router.put,
    "/{id}/visibility",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_save_visibility(
    request: Request,
    id: int,
    is_public: Annotated[bool, Body(embed=True)],
) -> SaveSchema:
    """Toggle a save's public/private visibility (owner only). A save a channel
    holds is shared with the channel."""
    save = _owned_save_or_404(id, request.user.id)
    assert_backup(save)

    updated = db_save_handler.update_save(id, {"is_public": is_public}, touch=False)

    # Keep the auto-captured thumbnail's visibility in sync so a shared save
    # still renders its preview for other users.
    if save.screenshot:
        db_screenshot_handler.update_screenshot(
            save.screenshot.id, {"is_public": is_public}
        )

    # Sharing a save exposes it to every other user's `has_saves` filter.
    if save.rom_id is not None:
        refresh_affected_smart_collections([save.rom_id], membership_only=True)

    return _build_save_schema(updated)


@protected_route(
    router.put,
    "/{id}/favorite",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_save_favorite(
    request: Request,
    id: int,
    is_favorite: Annotated[bool, Body(embed=True)],
) -> SaveSchema:
    """Favorite a save, sorting it ahead of the rest (owner only)."""
    _owned_save_or_404(id, request.user.id)

    return _build_save_schema(
        db_save_handler.update_save(id, {"is_favorite": is_favorite}, touch=False)
    )


@protected_route(
    router.put,
    "/{id}/labels",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_save_labels(
    request: Request,
    id: int,
    labels: Annotated[list[str], Body(embed=True)],
) -> SaveSchema:
    """Replace a save's free-text labels (owner only)."""
    _owned_save_or_404(id, request.user.id)

    return _build_save_schema(
        db_save_handler.update_save(
            id, {"labels": normalize_asset_labels(labels)}, touch=False
        )
    )


@protected_route(
    router.put,
    "/{id}/file-name",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def rename_save(
    request: Request,
    id: int,
    file_name: Annotated[str, Body(embed=True, max_length=FILE_NAME_MAX_LENGTH)],
) -> SaveSchema:
    """Rename a save's file, its screenshot following along (owner only)."""
    save = _owned_save_or_404(id, request.user.id)

    return _build_save_schema(await rename_asset(save, file_name))


@protected_route(
    router.post,
    "/delete",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def delete_saves(
    request: Request,
    saves: Annotated[
        list[int],
        Body(
            description="List of save ids to delete from database.",
            embed=True,
        ),
    ],
) -> list[int]:
    """Delete saves."""
    if not saves:
        error = "No saves were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    affected_rom_ids: set[int] = set()

    for save_id in saves:
        save = db_save_handler.get_save(user_id=request.user.id, id=save_id)
        if not save:
            error = f"Save with ID {save_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        assert_backup(save)

        affected_rom_ids.add(save.attached_rom_id)
        log.info(
            f"Deleting save {hl(save.file_name)} [{save.attached_rom.platform_slug}] from filesystem"
        )
        await remove_save(save)

    refresh_affected_smart_collections(list(affected_rom_ids), membership_only=True)

    return saves


@protected_route(router.post, "/{id}/track", [Scope.DEVICES_WRITE])
def track_save(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
) -> SaveSchema:
    """Re-enable sync tracking for a save on a device."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=False
    )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


@protected_route(router.post, "/{id}/untrack", [Scope.DEVICES_WRITE])
def untrack_save(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
) -> SaveSchema:
    """Disable sync tracking for a save on a device."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=True
    )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)
