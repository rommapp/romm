import json
import re
import uuid
import zipfile
from typing import Annotated, Any, Self

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from starlette.datastructures import UploadFile

from decorators.auth import protected_route
from endpoints.responses.snapshots import (
    DIGEST_PREFIX,
    CurrentRefSchema,
    MissingContentSchema,
    SnapshotConflictSchema,
    SnapshotSchema,
    build_snapshot_schema,
    can_read,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import get_rom_visibility_filter
from handler.database import (
    db_device_handler,
    db_rom_handler,
    db_save_handler,
    db_snapshot_handler,
)
from handler.filesystem.assets_handler import UnsafeArchive, check_upload
from handler.snapshots.clone import copy_part
from handler.snapshots.file_key import FileKey
from handler.snapshots.manifest import CARRY, Manifest, SaveEntry
from handler.snapshots.neutral import NeutralUnitRejected, check_neutral_unit
from handler.snapshots.write import (
    SAVE_PART,
    ChannelTarget,
    ContentMismatch,
    ContentMissing,
    FileMismatch,
    HardcoreDowngrade,
    LabelRequired,
    NotVisible,
    Outcome,
    SnapshotWrite,
    UploadPart,
    WriteResult,
    write_snapshot,
)
from models.assets import (
    EMULATOR_MAX_LENGTH,
    EMULATOR_VERSION_MAX_LENGTH,
    Save,
    SaveFormat,
    SaveShape,
)
from models.channel import CHANNEL_LABEL_MAX_LENGTH, Channel
from models.device import Device
from models.rom import Rom, RomFile
from models.snapshot import STATE_SLOT_MAX_LENGTH, Snapshot, SnapshotKind
from models.user import User
from utils.auth import create_or_find_web_device
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size, check_emulator_folder_name

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

HISTORY_PAGE_MAX = 100
SCREENSHOT_SUFFIX = ":screenshot"
SAVE_SCREENSHOT_PART = "save_screenshot"
STATE_PART_PATTERN = re.compile(r"^state:([^:]+):([^:]+)$")

ContentHash = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-fA-F]{32}$", to_lower=True)
]
CoreName = Annotated[
    str, StringConstraints(pattern=r"^[^:]+$", max_length=EMULATOR_MAX_LENGTH)
]
SlotName = Annotated[
    str, StringConstraints(pattern=r"^[^:]+$", max_length=STATE_SLOT_MAX_LENGTH)
]


class SaveEntryPayload(BaseModel):
    """A save by its hash, or by `copy_of`: a save of yours the server copies in."""

    hash: ContentHash | None = None
    copy_of: int | None = None
    shape: SaveShape | None = None
    format: SaveFormat | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.hash is None) == (self.copy_of is None):
            raise ValueError("a save names exactly one of `hash` and `copy_of`")
        if self.hash is not None and (self.shape is None or self.format is None):
            raise ValueError("a save by hash declares its `shape` and `format`")
        return self


class ManifestPayload(BaseModel):
    rom_file_id: int
    channel_id: uuid.UUID | None = None
    label: str | None = Field(
        default=None, min_length=1, max_length=CHANNEL_LABEL_MAX_LENGTH
    )
    expected_current_id: int | None
    parent_snapshot_id: int | None = None
    save: SaveEntryPayload | None = None
    states: dict[CoreName, dict[SlotName, ContentHash]] = {}
    is_hardcore: bool = False
    approve_hardcore_downgrade: bool = False
    emulator: str | None = Field(default=None, max_length=EMULATOR_MAX_LENGTH)
    emulator_version: str | None = Field(
        default=None, max_length=EMULATOR_VERSION_MAX_LENGTH
    )
    core: str | None = Field(default=None, max_length=EMULATOR_MAX_LENGTH)
    core_version: str | None = Field(
        default=None, max_length=EMULATOR_VERSION_MAX_LENGTH
    )

    def to_manifest(
        self, copied: SaveEntry | None = None, source: Save | None = None
    ) -> Manifest:
        """The manifest, with `copied` standing for a save named by `copy_of`.

        A push that names no emulator takes its copied `source`'s, which wrote the bytes.
        """
        ran = (self.emulator, self.emulator_version, self.core, self.core_version)
        if source is not None and not any(ran):
            ran = (
                source.emulator,
                source.emulator_version,
                source.core,
                source.core_version,
            )
        emulator, emulator_version, core, core_version = ran
        save: Any = CARRY
        if "save" in self.model_fields_set:
            save = None
            if copied is not None:
                save = copied
            elif self.save and self.save.hash:
                save = SaveEntry(
                    hash=self.save.hash, shape=self.save.shape, format=self.save.format
                )
        return Manifest(
            save=save,
            states=self.states,
            is_hardcore=self.is_hardcore,
            approve_hardcore_downgrade=self.approve_hardcore_downgrade,
            emulator=emulator,
            emulator_version=emulator_version,
            core=core,
            core_version=core_version,
        )


class SnapshotUpdatePayload(BaseModel):
    is_pinned: bool | None = None
    is_public: bool | None = None


def _not_found(what: str = "Snapshot") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found"
    )


def _readable(id: int, viewer: User) -> tuple[Snapshot, Channel | None]:
    snapshot = db_snapshot_handler.get_snapshot(id)
    if snapshot is None:
        raise _not_found()
    channel = (
        db_snapshot_handler.get_channel(snapshot.channel_id)
        if snapshot.channel_id
        else None
    )
    if not can_read(snapshot, channel, viewer):
        raise _not_found()
    return snapshot, channel


def visible_rom_file(request: Request, rom_file_id: int) -> tuple[RomFile, Rom]:
    rom_file = db_rom_handler.get_rom_file_by_id(rom_file_id)
    rom = db_rom_handler.get_rom(rom_file.rom_id) if rom_file else None
    if (
        rom_file is None
        or rom is None
        or not get_rom_visibility_filter(request).allows(rom)
    ):
        raise _not_found("ROM file")
    return rom_file, rom


def _own_device(device_id: str | None, user: User) -> Device | None:
    if device_id is None:
        return None
    device = db_device_handler.get_device(device_id=device_id, user_id=user.id)
    if device is None:
        raise _not_found("Device")
    return device


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_snapshots(
    request: Request,
    rom_file_id: Annotated[list[int] | None, Query()] = None,
    channel_id: uuid.UUID | None = None,
    current: bool = False,
    save_target: str | None = None,
    limit: Annotated[int, Query(ge=1, le=HISTORY_PAGE_MAX)] = 50,
    cursor: str | None = None,
) -> list[SnapshotSchema]:
    """Each channel's current snapshot on the named files, or one channel's history, newest first."""
    viewer = request.user
    if current:
        channels: dict[uuid.UUID, Channel] = {}
        for file_id in rom_file_id or []:
            rom_file, rom = visible_rom_file(request, file_id)
            for channel in db_snapshot_handler.get_channels_for_file(
                viewer.id, rom.platform_id, FileKey.of_file(rom_file)
            ):
                channels[channel.id] = channel
        if channel_id is not None:
            extra = db_snapshot_handler.get_channel(channel_id)
            if extra is None or (extra.user_id != viewer.id and not extra.is_public):
                raise _not_found("Channel")
            channels[extra.id] = extra
        results = []
        for channel in channels.values():
            if channel.current_snapshot_id is None:
                continue
            snapshot = db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
            if snapshot is None or (
                save_target is not None and snapshot.save_target != save_target
            ):
                continue
            results.append(build_snapshot_schema(snapshot, channel, viewer))
        return results

    if channel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="History needs a channel_id",
        )
    history = db_snapshot_handler.get_channel(channel_id)
    if history is None or (history.user_id != viewer.id and not history.is_public):
        raise _not_found("Channel")
    try:
        before_id = int(cursor) if cursor else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        ) from None
    return [
        build_snapshot_schema(snapshot, history, viewer)
        for snapshot in db_snapshot_handler.get_channel_history(
            history.id, limit, before_id=before_id, save_target=save_target
        )
    ]


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_snapshot(request: Request, id: int) -> SnapshotSchema:
    snapshot, channel = _readable(id, request.user)
    return build_snapshot_schema(snapshot, channel, request.user)


def _assert_shape(upload: UploadFile, shape: SaveShape) -> None:
    """A SINGLE save travels raw; MULTI and FOLDER travel as a zip."""
    upload.file.seek(0)
    is_zip = zipfile.is_zipfile(upload.file)
    upload.file.seek(0)
    if is_zip != (shape != SaveShape.SINGLE):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"save": f"the bytes are not a {shape.value} unit"},
        )


def _unprocessable(key: str, reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={key: reason}
    )


def _members(key: str, upload: UploadFile) -> list[str]:
    """The upload's archive entries, or its own name for a raw file."""
    try:
        names = check_upload(upload.file)
    except UnsafeArchive as exc:
        raise _unprocessable(key, str(exc)) from exc
    return names if names is not None else [upload.filename or key]


async def _read_push(
    request: Request,
) -> tuple[ManifestPayload, dict[str, UploadPart], list[str]]:
    """The push's manifest, its content parts, and the save part's members."""
    form = await request.form()
    raw = form.get("manifest")
    if not isinstance(raw, str):
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A manifest part is required",
            )
        raw = (await raw.read()).decode()
    try:
        payload = ManifestPayload.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                json.loads(exc.json()) if isinstance(exc, ValidationError) else str(exc)
            ),
        ) from exc

    uploads: dict[str, UploadFile] = {}
    for key, value in form.multi_items():
        if isinstance(value, str) or key == "manifest":
            continue
        check_asset_upload_size(value, key)
        uploads[key] = value

    parts: dict[str, UploadPart] = {}
    save_members: list[str] = []
    for key, upload in uploads.items():
        if key == SAVE_SCREENSHOT_PART or key.endswith(SCREENSHOT_SUFFIX):
            content_key = (
                SAVE_PART
                if key == SAVE_SCREENSHOT_PART
                else key.removesuffix(SCREENSHOT_SUFFIX)
            )
            if content_key not in uploads:
                if content_key != SAVE_PART and not STATE_PART_PATTERN.match(
                    content_key
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown part {key}",
                    )
                parts[content_key] = UploadPart(
                    content=None,
                    file_name=content_key.rsplit(":", 1)[-1],
                    screenshot=upload.file,
                    screenshot_name=upload.filename,
                )
            continue
        if key != SAVE_PART and not STATE_PART_PATTERN.match(key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown part {key}"
            )
        members = _members(key, upload)
        if key == SAVE_PART:
            save_members = members
        screenshot = uploads.get(
            SAVE_SCREENSHOT_PART if key == SAVE_PART else f"{key}{SCREENSHOT_SUFFIX}"
        )
        parts[key] = UploadPart(
            content=upload.file,
            file_name=upload.filename or key.rsplit(":", 1)[-1],
            screenshot=screenshot.file if screenshot else None,
            screenshot_name=screenshot.filename if screenshot else None,
        )
    if payload.save and payload.save.shape and SAVE_PART in uploads:
        _assert_shape(uploads[SAVE_PART], payload.save.shape)
    return payload, parts, save_members


def _clone_origin(
    request: Request,
    payload: ManifestPayload,
    parts: dict[str, UploadPart],
    copied: SaveEntry | None,
    copied_from: str | None,
) -> str:
    """The device a push with no device attributes its snapshot to.

    A copy keeps the device that wrote the source bytes, and a push that sends
    no bytes reuses its parent's content, so it keeps the parent's device. Bytes
    the browser uploads, or a source with no device, belong to the web UI.
    """
    if copied is not None:
        if copied_from:
            return copied_from
    elif all(part.content is None for part in parts.values()):
        parent_id = (
            payload.parent_snapshot_id
            if "parent_snapshot_id" in payload.model_fields_set
            else payload.expected_current_id
        )
        parent = db_snapshot_handler.get_snapshot(parent_id) if parent_id else None
        if parent is not None and parent.origin_device_id:
            return parent.origin_device_id
    return create_or_find_web_device(request, request.user).id


def _respond(result: WriteResult, viewer: User) -> JSONResponse:
    channel = (
        db_snapshot_handler.get_channel(result.snapshot.channel_id)
        if result.snapshot.channel_id
        else None
    )
    body = build_snapshot_schema(result.snapshot, channel, viewer)
    if result.outcome == Outcome.BRANCHED:
        current = result.current
        conflict = SnapshotConflictSchema(
            current=(
                CurrentRefSchema(
                    id=current.id, digest=f"{DIGEST_PREFIX}{current.digest}"
                )
                if current
                else None
            ),
            branch=body,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )
    code = (
        status.HTTP_200_OK
        if result.outcome == Outcome.UNCHANGED
        else status.HTTP_201_CREATED
    )
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"))


@protected_route(
    router.post,
    "",
    [Scope.ASSETS_WRITE],
    response_model=SnapshotSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"model": SnapshotSchema},
        status.HTTP_400_BAD_REQUEST: {"model": MissingContentSchema},
        status.HTTP_409_CONFLICT: {"model": SnapshotConflictSchema},
    },
)
async def push_snapshot(request: Request, device_id: str | None = None) -> JSONResponse:
    """Write a snapshot into a channel. Multipart: a `manifest` JSON part, plus
    `save`, `state:<core>:<slot>` and their screenshot parts for hashes the server lacks.
    A screenshot part may come alone, for content the server holds without one.
    """
    viewer = request.user
    device = _own_device(device_id, viewer)
    payload, parts, save_members = await _read_push(request)
    check_emulator_folder_name(payload.emulator)
    rom_file, rom = visible_rom_file(request, payload.rom_file_id)
    if (
        payload.save
        and payload.save.format == SaveFormat.NEUTRAL
        and payload.save.shape
        and SAVE_PART in parts
    ):
        try:
            check_neutral_unit(rom.platform_slug, payload.save.shape, save_members)
        except NeutralUnitRejected as exc:
            raise _unprocessable("save", str(exc)) from exc

    copied: SaveEntry | None = None
    copied_from: str | None = None
    source: Save | None = None
    if payload.save and payload.save.copy_of is not None:
        source = db_save_handler.get_save(user_id=viewer.id, id=payload.save.copy_of)
        if source is None:
            raise _not_found("Save")
        copied, parts[SAVE_PART] = await copy_part(
            source, payload.save.shape, payload.save.format
        )
        copied_from = source.origin_device_id

    write = SnapshotWrite(
        author=viewer,
        rom=rom,
        rom_file=rom_file,
        manifest=payload.to_manifest(copied, source),
        channel=ChannelTarget(
            expected_current_id=payload.expected_current_id,
            id=payload.channel_id,
            label=payload.label,
        ),
        parent_snapshot_id=(
            payload.parent_snapshot_id
            if "parent_snapshot_id" in payload.model_fields_set
            else CARRY
        ),
        device_id=device.id if device else None,
        origin_device_id=(
            device.id
            if device
            else _clone_origin(request, payload, parts, copied, copied_from)
        ),
        parts=parts,
    )
    try:
        result = await write_snapshot(write)
    except ContentMissing as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=MissingContentSchema(missing=exc.keys).model_dump(),
        )
    except NotVisible as exc:
        raise _not_found(exc.what.capitalize()) from exc
    except (FileMismatch, ContentMismatch, LabelRequired) as exc:
        field = "rom_file_id" if isinstance(exc, FileMismatch) else "manifest"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={field: str(exc)}
        ) from exc
    except HardcoreDowngrade:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"hardcore_downgrade": True}
        )
    return _respond(result, viewer)


@protected_route(router.patch, "/{id}", [Scope.ASSETS_WRITE])
def update_snapshot(
    request: Request, id: int, payload: SnapshotUpdatePayload
) -> SnapshotSchema:
    """Pin a snapshot, or share an archival one."""
    viewer = request.user
    snapshot, channel = _readable(id, viewer)
    changes: dict[str, Any] = {}
    if payload.is_pinned is not None:
        changes["is_pinned"] = payload.is_pinned
    if payload.is_public is not None:
        if snapshot.kind != SnapshotKind.ARCHIVAL or snapshot.user_id != viewer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the owner of an archival snapshot shares it",
            )
        changes["is_public"] = payload.is_public
    if changes:
        snapshot = db_snapshot_handler.update_snapshot(snapshot.id, changes)
    if "is_public" in changes:
        content = db_snapshot_handler.get_stored_content(snapshot)
        db_snapshot_handler.sync_content_visibility(
            [content.save.id] if content.save else [],
            [state.id for slots in content.states.values() for state in slots.values()],
        )
    return build_snapshot_schema(snapshot, channel, viewer)


@protected_route(
    router.put,
    "/{id}/devices/{device_id}",
    [Scope.DEVICES_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
def report_applied(request: Request, id: int, device_id: str) -> None:
    """Record the snapshot a device applied after a download, for attribution."""
    device = _own_device(device_id, request.user)
    snapshot, channel = _readable(id, request.user)
    if device is None or channel is None:
        raise _not_found()
    db_snapshot_handler.record_device_base(device.id, channel.id, snapshot.id)
