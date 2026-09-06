"""Response shapes for the streaming routes.

Declared rather than returned as bare dicts, so they reach the OpenAPI schema
and generate into the frontend's types.
"""

from typing import Literal

from .base import BaseModel


class SlotCapabilitiesSchema(BaseModel):
    """What save-state controls a platform's emulator actually exposes."""

    max_slots: int
    has_autosave: bool
    autosave_slot: int
    has_memory_card: bool
    supports_disc_swap: bool
    has_manual_disc_swap: bool


class StreamingContainerSchema(BaseModel):
    """One platform the fleet can stream, as the play screen needs it."""

    platform: str
    host: str
    label: str
    capabilities: SlotCapabilitiesSchema
    emulator: str
    supports_memory_cards: bool


class StreamingConfigSchema(BaseModel):
    enabled: bool
    containers: list[StreamingContainerSchema]


class SessionTerminationSchema(BaseModel):
    """Why a session the caller held is gone, left behind for their next poll.

    Only an admin force-release records one; a session the player released or
    that simply expired leaves no notice.
    """

    ended_by: str | None = None
    reason: str | None = None
    ended_at: str | None = None
    platform: str | None = None
    rom_id: int | None = None
    rom_name: str | None = None


class SessionStatusSchema(BaseModel):
    status: Literal["active", "ended"]
    platform: str
    extraction_phase: str | None = None
    """Set while a webstation broker unpacks a pkg or archive, which is the
    part of a launch long enough that the player needs to see something."""
    termination: SessionTerminationSchema | None = None


class LaunchingSessionSchema(BaseModel):
    """The 202 a claim answers with: the container is reserved and the game is
    on its way up. The room URL follows over the socket, since only the
    broker's launch reply carries it."""

    platform: str
    container: str
    label: str
    rom_name: str
    claimed_at: str


class LaunchReadyPayload(BaseModel):
    """`streaming:launch-ready`, pushed once the game is up."""

    platform: str
    container: str
    host: str
    resume: bool | None = None
    """None when no resume was asked for; False means the state could not be
    pushed and the session started fresh."""


class LaunchFailedPayload(BaseModel):
    """`streaming:launch-failed`. The claim is already released."""

    platform: str
    container: str
    detail: str


class LaunchPhasePayload(BaseModel):
    """`streaming:launch-phase`, while a broker unpacks a large title."""

    platform: str
    container: str
    phase: str | None = None


class DesktopSessionSchema(BaseModel):
    container: str
    platform: str
    host: str
    label: str
    claimed_at: str


class JoinedSessionSchema(BaseModel):
    platform: str
    host: str
    label: str
    rom_id: int | None = None
    rom_name: str | None = None


class SaveAndExitResponse(BaseModel):
    status: Literal["ok"]
    saved: bool
    platform: str
    released: bool


class ReleaseSessionResponse(BaseModel):
    status: Literal["released", "not_found"]
    platform: str


class ForceReleaseResponse(BaseModel):
    status: Literal["released"]
    platforms: list[str]


class VolumeResponse(BaseModel):
    status: Literal["ok"]
    level: int
    platform: str


class MuteResponse(BaseModel):
    status: Literal["ok"]
    mute: bool | None = None
    platform: str


class SaveStateResponse(BaseModel):
    status: Literal["saving"]
    slot: int
    platform: str


class LoadStateResponse(BaseModel):
    status: Literal["ok"]
    loaded: bool
    slot: int
    platform: str


class SwapDiscResponse(BaseModel):
    status: Literal["ok"]
    file_id: int
    platform: str


class StateFrameResponse(BaseModel):
    status: Literal["ok"]
    platform: str


class JoinableSessionSchema(BaseModel):
    """A session its host opened to other players, plus enough of the ROM to
    draw a cover tile without a second request per session."""

    container: str
    label: str | None = None
    platform: str | None = None
    rom_id: int | None = None
    rom_name: str | None = None
    host_username: str | None = None
    claimed_at: str | None = None
    platform_id: int | None = None
    platform_display_name: str | None = None
    path_cover_small: str | None = None
    path_cover_large: str | None = None
    url_cover: str | None = None


class JoinableSessionsResponse(BaseModel):
    sessions: list[JoinableSessionSchema]


class AdminSessionSchema(BaseModel):
    container: str
    label: str | None = None
    platform: str | None = None
    rom_id: int | None = None
    rom_name: str | None = None
    desktop: bool
    claimed_at: str | None = None
    user_id: int | None = None
    username: str | None = None


class AdminSessionsResponse(BaseModel):
    sessions: list[AdminSessionSchema]


class ContainerSessionSchema(BaseModel):
    """Whatever a container is running, as the fleet view shows it."""

    platform: str | None = None
    rom_id: int | None = None
    rom_name: str | None = None
    desktop: bool
    claimed_at: str | None = None
    user_id: int | None = None
    username: str | None = None


class AdminContainerSchema(BaseModel):
    container: str
    label: str | None = None
    host: str
    platforms: list[str]
    supports_desktop: bool
    configured: bool
    """False for a container with no usable broker address: it can never be
    claimed, and saying so beats listing it as idle."""
    session: ContainerSessionSchema | None = None


class AdminContainersResponse(BaseModel):
    enabled: bool
    containers: list[AdminContainerSchema]


class MemoryCardSummarySchema(BaseModel):
    """What is on the card a container is holding, enough for the player to
    recognise it before deciding whether to keep it."""

    file_count: int
    total_bytes: int
    game_codes: list[str]


class MemoryCardImportRequired(BaseModel):
    """The 428 body: a container still holds a card nobody has decided about.

    The claim is not held open behind the prompt; the answer comes back on a
    fresh claim as `card_import`.
    """

    code: Literal["memory_card_import_required"]
    outcome: Literal["found", "unreadable"]
    summary: MemoryCardSummarySchema | None = None
    reason: str | None = None
