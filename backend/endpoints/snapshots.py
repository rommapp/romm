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
    build_snapshot_schemas,
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
from handler.snapshots.shared_card import own_saves_only
from handler.snapshots.write import (
    INFER,
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
from utils.auth import create_or_find_web_device, token_device_id
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size, check_emulator_folder_name

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

HISTORY_PAGE_MAX = 100
FEED_DEVICE_DESCRIPTION = (
    "The device fetching the feed, else the client token's. Listing a channel's "
    "current for a device records it as the current the device knows, which a "
    "push without `expected_current_id` expects. Naming one takes `devices.write`."
)
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
    expected_current_id: int | None = Field(
        default=None,
        description=(
            "The current snapshot the push builds on; null expects an empty channel. "
            "Left out, the push expects the latest current its device knows from a "
            "feed, push or download, else its parent, else an empty channel."
        ),
    )
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


def rom_hidden(request: Request, rom_id: int | None) -> bool:
    """Whether the ROM a channel or snapshot is on is hidden from the caller,
    which hides the channel and its snapshots too."""
    if rom_id is None:
        return False
    # Channels of one file share their ROM, so a listing asks once per ROM.
    known: dict[int, bool] | None = getattr(request.state, "rom_hidden", None)
    if known is None:
        known = request.state.rom_hidden = {}
    if rom_id not in known:
        rom = db_rom_handler.get_rom_visibility(rom_id)
        known[rom_id] = rom is not None and not get_rom_visibility_filter(
            request
        ).allows(rom)
    return known[rom_id]


def readable_channel(request: Request, channel: Channel) -> bool:
    return (channel.user_id == request.user.id or channel.is_public) and not rom_hidden(
        request, channel.rom_id
    )


def _readable(request: Request, id: int) -> tuple[Snapshot, Channel | None]:
    snapshot = db_snapshot_handler.get_snapshot(id)
    if snapshot is None:
        raise _not_found()
    channel = (
        db_snapshot_handler.get_channel(snapshot.channel_id)
        if snapshot.channel_id
        else None
    )
    if not snapshot.readable_by(request.user.id, channel) or rom_hidden(
        request, snapshot.rom_id
    ):
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


def _own_device(request: Request, device_id: str | None) -> Device | None:
    """The caller's device a write is attributed to. Naming one takes
    `devices.write`, as the legacy save upload requires, unless it is the
    device the client token is bound to."""
    if device_id is None:
        return None
    if Scope.DEVICES_WRITE not in request.auth.scopes and device_id != token_device_id(
        request
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if device is None:
        raise _not_found("Device")
    return device


def request_device(request: Request, device_id: str | None) -> Device | None:
    """The device a request acts for: `device_id`, on `_own_device`'s terms,
    else the device its client token is bound to, which needs no `devices.write`."""
    if device_id is not None:
        return _own_device(request, device_id)
    bound = token_device_id(request)
    if bound is None:
        return None
    return db_device_handler.get_device(device_id=bound, user_id=request.user.id)


def required_device(request: Request, device_id: str | None) -> Device:
    """`request_device`, which a request that acts on a device's state needs.

    Raises:
        HTTPException: 400 when the request names no device and its token has none.
    """
    device = request_device(request, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A device is required"
        )
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
    device_id: Annotated[str | None, Query(description=FEED_DEVICE_DESCRIPTION)] = None,
) -> list[SnapshotSchema]:
    """Each channel's current snapshot on the named files, or one channel's history, newest first.

    Records each current it lists as the one the device knows: every channel
    of a `current` listing, and a history page holding the channel's current
    without a `cursor`.
    """
    viewer = request.user
    device = request_device(request, device_id)
    if current:
        channels: dict[uuid.UUID, Channel] = {}
        for file_id in rom_file_id or []:
            rom_file, rom = visible_rom_file(request, file_id)
            for channel in db_snapshot_handler.get_channels_for_file(
                viewer.id, rom.platform_id, FileKey.of_file(rom_file)
            ):
                if readable_channel(request, channel):
                    channels[channel.id] = channel
        if channel_id is not None:
            extra = db_snapshot_handler.get_channel(channel_id)
            if extra is None or not readable_channel(request, extra):
                raise _not_found("Channel")
            channels[extra.id] = extra
        currents = db_snapshot_handler.get_snapshots(
            {c.current_snapshot_id for c in channels.values() if c.current_snapshot_id}
        )
        listed = [
            (currents[c.current_snapshot_id], c)
            for c in channels.values()
            if c.current_snapshot_id in currents
            and (
                save_target is None
                or currents[c.current_snapshot_id].save_target == save_target
            )
        ]
        if device is not None:
            db_snapshot_handler.record_device_seen(
                device.id, {c.id: snapshot.id for snapshot, c in listed}
            )
        return build_snapshot_schemas(listed, viewer)

    if channel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="History needs a channel_id",
        )
    history = db_snapshot_handler.get_channel(channel_id)
    if history is None or not readable_channel(request, history):
        raise _not_found("Channel")
    try:
        before_id = int(cursor) if cursor else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        ) from None
    page = db_snapshot_handler.get_channel_history(
        history.id, limit, before_id=before_id, save_target=save_target
    )
    if (
        device is not None
        and cursor is None
        and (
            history.current_snapshot_id is None
            or any(snapshot.id == history.current_snapshot_id for snapshot in page)
        )
    ):
        db_snapshot_handler.record_device_seen(
            device.id, {history.id: history.current_snapshot_id}
        )
    return build_snapshot_schemas([(snapshot, history) for snapshot in page], viewer)


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_snapshot(
    request: Request,
    id: int,
    device_id: Annotated[
        str | None,
        Query(
            description="The device `hold` records for, else the client token's; takes `devices.write`."
        ),
    ] = None,
    hold: Annotated[
        bool,
        Query(
            description="Records the snapshot as the one the device holds, as a download it applies."
        ),
    ] = False,
) -> SnapshotSchema:
    """One snapshot. With `hold`, records it as the snapshot the device holds
    in its channel, and as the current the device knows when it is the
    channel's current. `hold` without a device is a 400."""
    device = required_device(request, device_id) if hold else None
    snapshot, channel = _readable(request, id)
    if device is not None and channel is not None:
        db_snapshot_handler.record_device_base(device.id, channel.id, snapshot.id)
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


def _named_parent(payload: ManifestPayload) -> Snapshot | None:
    """The parent the push names, else the expected current it carries from."""
    parent_id = (
        payload.parent_snapshot_id
        if "parent_snapshot_id" in payload.model_fields_set
        else payload.expected_current_id
    )
    return db_snapshot_handler.get_snapshot(parent_id) if parent_id else None


def _assert_parent_visible(request: Request, parent: Snapshot | None) -> None:
    """404 for a parent on a ROM hidden from the caller, as reading it would be."""
    if parent is not None and rom_hidden(request, parent.rom_id):
        raise _not_found("Parent snapshot")


def _clone_origin(
    request: Request,
    parent: Snapshot | None,
    parts: dict[str, UploadPart],
    copied: SaveEntry | None,
    copied_from: str | None,
) -> str:
    """The device a push with no device attributes its snapshot to: the
    caller's device that wrote the bytes it copies or reuses, else the web UI."""
    if copied is not None:
        if copied_from:
            return copied_from
    elif (
        all(part.content is None for part in parts.values())
        and parent is not None
        and parent.origin_device_id
        and db_device_handler.get_device(
            device_id=parent.origin_device_id, user_id=request.user.id
        )
    ):
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
        assert result.conflict is not None, "a branched write names its conflict"
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
            reason=result.conflict,
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
        status.HTTP_403_FORBIDDEN: {},
        status.HTTP_409_CONFLICT: {"model": SnapshotConflictSchema},
    },
)
async def push_snapshot(request: Request, device_id: str | None = None) -> JSONResponse:
    """Write a snapshot into a channel. Multipart: a `manifest` JSON part, plus
    `save`, `state:<core>:<slot>` and their screenshot parts for hashes the server lacks.
    A screenshot part may come alone, for content the server holds without one.
    A native PS1, PS2 or GameCube card holding other games' saves is stored as
    this game's per-game unit, in neutral form. Naming `device_id` also takes
    `devices.write`, and the device must be the caller's own. Without it, a
    device-bound client token's device is the push's.
    """
    viewer = request.user
    device = request_device(request, device_id)
    payload, parts, save_members = await _read_push(request)
    check_emulator_folder_name(payload.emulator)
    rom_file, rom = visible_rom_file(request, payload.rom_file_id)
    target = (
        db_snapshot_handler.get_channel(payload.channel_id)
        if payload.channel_id
        else None
    )
    if target is not None and rom_hidden(request, target.rom_id):
        raise _not_found("Channel")
    parent = _named_parent(payload)
    _assert_parent_visible(request, parent)
    save_part = parts.get(SAVE_PART)
    if (
        payload.save
        and payload.save.format == SaveFormat.NEUTRAL
        and payload.save.shape
        and save_part is not None
        and save_part.content is not None
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
        try:
            copied, parts[SAVE_PART] = await copy_part(
                source, payload.save.shape, payload.save.format
            )
        except FileNotFoundError as exc:
            raise _not_found("Save file") from exc
        copied_from = source.origin_device_id

    write = SnapshotWrite(
        author=viewer,
        rom=rom,
        rom_file=rom_file,
        manifest=payload.to_manifest(copied, source),
        channel=ChannelTarget(
            expected_current_id=(
                payload.expected_current_id
                if "expected_current_id" in payload.model_fields_set
                else INFER
            ),
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
            else _clone_origin(request, parent, parts, copied, copied_from)
        ),
        parts=parts,
    )
    try:
        result = await write_snapshot(await own_saves_only(write))
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
    """Pin or unpin a snapshot for the caller, which any reader may do, or share
    an archival one, which only its owner may do."""
    viewer = request.user
    snapshot, channel = _readable(request, id)
    if payload.is_public is not None:
        if snapshot.user_id != viewer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the owner of a snapshot shares it",
            )
        if snapshot.kind != SnapshotKind.ARCHIVAL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an archival snapshot is shared on its own",
            )
    if payload.is_pinned is not None:
        db_snapshot_handler.set_pin(snapshot.id, viewer.id, payload.is_pinned)
    if payload.is_public is not None:
        snapshot = db_snapshot_handler.update_snapshot(
            snapshot.id, {"is_public": payload.is_public}
        )
        if not payload.is_public:
            db_snapshot_handler.drop_foreign_pins(
                snapshot.user_id, snapshot_id=snapshot.id
            )
        content = db_snapshot_handler.get_stored_content(snapshot)
        db_snapshot_handler.sync_content_visibility(
            [content.save.id] if content.save else [],
            [state.id for state in content.state_rows],
        )
    return build_snapshot_schema(snapshot, channel, viewer)


@protected_route(
    router.put,
    "/{id}/devices/{device_id}",
    [Scope.ASSETS_READ],
    status_code=status.HTTP_204_NO_CONTENT,
)
def report_applied(request: Request, id: int, device_id: str) -> None:
    """Record the snapshot a device applied after a download, as
    `GET /snapshots/{id}?hold=true` does. Naming a device takes `devices.write`
    unless it is the one the client token is bound to."""
    device = _own_device(request, device_id)
    snapshot, channel = _readable(request, id)
    if device is None or channel is None:
        raise _not_found()
    db_snapshot_handler.record_device_base(device.id, channel.id, snapshot.id)
