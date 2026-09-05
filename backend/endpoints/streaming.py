"""Streaming session routes.

Reads gate on ROMS_READ; anything that creates, controls or releases a session
gates on ROMS_USER_WRITE, matching the play-session routes. ROMS_USER_WRITE is
always-on for authenticated users, so this costs no real user anything, but it
is absent from READ_SCOPES -- which is all KIOSK_MODE hands an anonymous
visitor. Without it, kiosk visitors (who all share one synthetic user, so
session ownership cannot separate them) could claim sessions and overwrite
each other's save states.
"""

import asyncio
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, NamedTuple

from fastapi import BackgroundTasks, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.streaming import (
    AdminContainersResponse,
    AdminSessionsResponse,
    DesktopSessionSchema,
    ForceReleaseResponse,
    JoinableSessionsResponse,
    JoinedSessionSchema,
    LaunchingSessionSchema,
    LoadStateResponse,
    MemoryCardImportRequired,
    MemoryCardSummarySchema,
    MuteResponse,
    ReleaseSessionResponse,
    SaveAndExitResponse,
    SaveStateResponse,
    SessionStatusSchema,
    StateFrameResponse,
    StreamingConfigSchema,
    SwapDiscResponse,
    VolumeResponse,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import (
    db_container_adoption_handler,
    db_rom_handler,
    db_user_handler,
)
from handler.redis_handler import async_cache
from handler.streaming import (
    access,
    background,
    commands,
    languages,
    launch,
    lifecycle,
    memory_cards,
    saves,
    states,
    webstation,
)
from handler.streaming.capabilities import (
    MAX_SLOT,
    PlatformCapabilities,
    slot_capabilities,
)
from handler.streaming.config import (
    ResolvedContainer,
    configured_emulator,
    container_for_session,
    containers_by_key,
    containers_for_platform,
    resolve_containers,
    streaming_enabled,
)
from handler.streaming.protocol import room_url_on
from handler.streaming.session_store import (
    STREAMING_SESSION_DRAIN_SECONDS,
    STREAMING_SESSION_TTL_SECONDS,
    StreamingSessionContended,
    claim_drain_marker,
    clear_termination,
    get_live_session,
    get_session,
    get_termination,
    iter_live_sessions,
    iter_session_keys,
    mutate_session,
    record_termination,
    refresh_session,
    release_own_session,
    session_disc_id,
    session_is_stale,
    session_redis_key,
    set_session_disc,
    stamp_launched,
)
from logger.logger import log
from models.assets import MemoryCard, MemoryCardVersion
from models.rom import Rom
from models.user import Role
from utils.m3u import playlist_files
from utils.router import APIRouter

router = APIRouter(prefix="/streaming", tags=["streaming"])


class ClaimStreamingSessionRequest(BaseModel):
    rom_id: Annotated[int, Field(ge=1)]
    # Optional state to resume from: the backend pushes its file to the broker
    # before launch and the broker loads its slot once the game is up. Must be
    # the claiming user's own state or a public one shared by another user.
    state_id: Annotated[int, Field(ge=1)] | None = None
    # Optional memory card to mount (whole-card sync containers only). Omitted =
    # the user's most-recently-used card for the emulator, or a fresh one on
    # first play. Must be one the claiming user owns.
    memory_card_id: Annotated[int, Field(ge=1)] | None = None
    # Answer to the one-time import prompt on a container whose pre-existing
    # card has never been adopted. "adopt" keeps it, "discard" wipes it, and
    # "discard" doubles as the override for a card that could not be read.
    card_import: Literal["adopt", "discard"] | None = None
    # Decided on the launch screen and fixed for the session. True advertises
    # the session on GET /sessions/joinable and tells the room to show its
    # comms surface while the host is still alone.
    multiplayer: bool = False


class SaveAndExitRequest(BaseModel):
    # 0 leaves the slot to the broker's own exit save. Anything else is a
    # coarse union bound here and the exact per-platform ceiling in the route.
    slot: Annotated[int, Field(ge=0, le=MAX_SLOT)] = 0
    wait: bool = True


class VolumeRequest(BaseModel):
    level: Annotated[int, Field(ge=0, le=100)]


class MuteRequest(BaseModel):
    mute: bool | None = None  # None = toggle, True/False = explicit set


class SaveStateRequest(BaseModel):
    # Coarse union bound (widest is the autosave slot); the route validates the
    # exact per-platform ceiling with _assert_valid_slot.
    slot: Annotated[int, Field(ge=1, le=MAX_SLOT)] = 1


class SwapDiscRequest(BaseModel):
    file_id: Annotated[int, Field(ge=1)]


class LoadStateRequest(BaseModel):
    # Coarse union bound (widest is the autosave slot); the route validates the
    # exact per-platform ceiling with _assert_valid_slot.
    slot: Annotated[int, Field(ge=1, le=MAX_SLOT)] = 1


class DesktopStreamingSessionRequest(BaseModel):
    # The container to open, named by the key GET /streaming/containers
    # reports. Named rather than pooled: an admin configuring a container
    # needs that one, not whichever is free.
    container: Annotated[str, Field(min_length=1, max_length=300)]


def platform_capabilities(platform: str) -> PlatformCapabilities:
    """Save-state and disc capabilities for a platform, resolved through
    whichever emulator a container is configured to serve it with."""
    return slot_capabilities(platform, configured_emulator(platform))


def _assert_valid_slot(platform: str, slot: int) -> None:
    """Reject a slot the platform does not expose before hitting the broker."""
    caps = platform_capabilities(platform)
    valid = 1 <= slot <= caps["max_slots"]
    if caps["has_autosave"] and slot == caps["autosave_slot"]:
        valid = True
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"Slot {slot} is not available for platform '{platform}'",
        )


def _swappable_disc_file_ids(rom: Rom) -> set[int]:
    """The rom files that are valid swap targets: the ROM's playlist entries."""
    return {f.id for f in playlist_files(rom.files)}


async def _session_status(platform: str, request: Request) -> dict[str, Any]:
    """Whether the caller still holds this platform's session, and if not, why
    it ended. Read-only, so it is safe to poll."""
    candidates = containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )
    found = await access.find_session_for_user(candidates, request.user.id)
    if found is not None:
        container, _, session = found
        status: dict[str, Any] = {"status": "active", "platform": platform}
        # An activate that has not returned yet leaves no launched_at behind.
        # Gating the broker round trip on it keeps this route pure Redis for
        # the rest of the session, which is the part that gets polled forever.
        if (
            session.get("launched_at") is None
            and container.protocol.reports_launch_phase
        ):
            status["extraction_phase"] = await asyncio.to_thread(
                webstation.launch_phase, container
            )
        return status
    # The tombstone is keyed per container, so with a pool the caller's notice
    # can sit under any of them.
    termination = None
    for candidate in candidates:
        termination = await get_termination(candidate.key, request.user.id)
        if termination is not None:
            break
    return {
        "status": "ended",
        "platform": platform,
        "termination": termination,
    }


async def _read_capped_body(request: Request, max_bytes: int) -> bytes | None:
    """The request body, or None once it goes past `max_bytes`.

    `Request.body()` buffers everything the client sends before any check can
    look at the size, so the cap is applied as the chunks arrive instead.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        return None

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _joinable_container_label(
    grouped: dict[str, list[ResolvedContainer]], container_key: str
) -> str | None:
    """What to call the box a joinable session runs on. The container's own
    label, not the per-platform one: the row names a container, not a game."""
    entries = grouped.get(container_key)
    if not entries:
        return None
    return entries[0].container_label or entries[0].label


@protected_route(router.get, "/config", [Scope.ROMS_READ])
async def get_config(request: Request) -> StreamingConfigSchema:
    """Return streaming configuration to the frontend"""
    # Keyed by platform: a pool is a backend concern, the frontend picks a
    # platform and the claim decides which container serves it.
    safe_containers: dict[str, dict[str, Any]] = {}
    for c in resolve_containers():
        if c.platform in safe_containers:
            continue
        # The record carries the platform's label and capabilities, so a
        # platform hidden from this caller must not be listed here either.
        if not access.platform_is_visible(request, c.platform):
            continue
        safe_containers[c.platform] = {
            "platform": c.platform,
            "host": c.host,
            "label": c.label,
            # Ship slot capabilities so the frontend selector reads them
            # instead of keeping its own hardcoded per-platform copy.
            "capabilities": c.capabilities,
            # State namespace for this container, so the frontend can
            # filter the resume picker the same way hydration filters.
            "emulator": c.emulator,
            # Whether this container syncs whole memory cards, so the
            # frontend only offers the card picker where it applies.
            "supports_memory_cards": c.memory_card_sync,
        }

    return StreamingConfigSchema(
        enabled=streaming_enabled(), containers=list(safe_containers.values())
    )


async def _win_container(
    request: Request,
    candidates: list[ResolvedContainer],
    session: dict[str, Any],
    platform: str,
) -> ResolvedContainer:
    """Reserve one of the platform's containers for this claim.

    Raises 409 when every one of them is held, with enough of the holder for
    the launch screen to say what the player is waiting on.
    """

    async def try_claim(candidate: ResolvedContainer) -> bool:
        # SET NX is atomic: exactly one concurrent claim wins the key. The TTL
        # bounds how long an abandoned session (broker dead / backend crashed)
        # can hold the container; control calls and heartbeats refresh it.
        return bool(
            await async_cache.set(
                session_redis_key(candidate.key),
                json.dumps(session),
                nx=True,
                ex=STREAMING_SESSION_TTL_SECONDS,
            )
        )

    # Config order, first free wins.
    for candidate in candidates:
        if await try_claim(candidate):
            return candidate

    # Every container is held, but a holder may be long gone: a closed tab or a
    # crashed browser never sends a release, and the TTL alone would hold it for
    # hours. A stale heartbeat means abandoned, so tear that session down
    # (evacuating its card and crediting its playtime) and retry. Evicting
    # anyone is deferred until here so a pool never displaces a stale session
    # while another container sits idle. A drain marker is never taken over: an
    # exit still has the broker killing the emulator or the state coming out of
    # it, and the marker only outlives that work by _DRAIN_MARKER_TTL, since the
    # backend doing it is what refreshes it.
    deadline = time.monotonic() + lifecycle.ABANDONED_TEARDOWN_WAIT
    for candidate in candidates:
        existing = await get_session(candidate.key)
        if (
            existing is None
            or existing.get("draining")
            or not session_is_stale(existing)
        ):
            continue
        log.warning(
            "taking over stale session, platform=%s user_id=%s",
            platform,
            existing.get("user_id"),
        )
        if not await lifecycle.await_teardown_within_budget(
            candidate,
            candidate.key,
            existing,
            max(0.0, deadline - time.monotonic()),
        ):
            continue
        if await try_claim(candidate):
            return candidate

    # Report the head of the pool as the holder: with one container that is the
    # only holder, and with several the player just needs to know the platform
    # is busy.
    existing = await get_session(candidates[0].key) or {}
    # A drain marker belongs to nobody: the previous session is over and its
    # exit state is still coming out of the container, so rom_name and
    # claimed_at are both blank and "in use" would name no one. The player who
    # just pressed save-and-exit sees this, and needs to be told to wait rather
    # than that somebody else took their platform.
    draining = bool(existing.get("draining"))
    if draining:
        message = "The previous session is still saving, try again shortly"
    elif len(candidates) == 1:
        message = "Session in use"
    else:
        message = f"All {len(candidates)} containers for this platform are in use"
    raise HTTPException(
        status_code=409,
        detail={
            "message": message,
            "draining": draining,
            "rom_name": access.visible_rom_name(request, existing),
            "claimed_at": existing.get("claimed_at"),
        },
    )


class _ContainerCard(NamedTuple):
    """What a claim found in the container's own memory-card slot.

    `undecided` is False when the answer was already on record, which is every
    claim after the first one on a given container.
    """

    undecided: bool = False
    content: bytes | None = None


async def _probe_container_card(
    container: ResolvedContainer,
    session: dict[str, Any],
    card_import: Literal["adopt", "discard"] | None,
) -> _ContainerCard:
    """Read the card a container still holds, prompting when nobody has said
    what to do with it.

    A container that still holds someone's pre-existing card must not be wiped
    on a hunch. Probe once, then the caller records the answer so this never
    interrupts a claim again. Probed only by the claim winner, so a user who
    loses the race gets the 409 rather than a prompt describing the card of the
    player currently on the container. Every exit from here that is not a
    started session releases the claim, so an abandoned dialog leaves no trace.
    """
    if (
        not container.memory_card_sync
        or db_container_adoption_handler.get_adoption(container.key) is not None
    ):
        return _ContainerCard()

    try:
        content = await asyncio.to_thread(memory_cards.fetch_card, container)
    except memory_cards.MemoryCardUnavailable as exc:
        # Unreadable is not empty, so the wipe needs the user's consent. Only
        # "discard" may override it: a card that was never captured cannot be
        # adopted, and pretending otherwise destroys it.
        log.warning("could not read the container memory card, %s", exc)
        if card_import == "discard":
            return _ContainerCard(undecided=True)
        await lifecycle.abort_claim(container.key, session)
        if card_import is None:
            raise HTTPException(
                status_code=428,
                detail=MemoryCardImportRequired(
                    code="memory_card_import_required",
                    outcome="unreadable",
                    reason=memory_cards.CARD_UNREADABLE_REASON,
                ).model_dump(),
            ) from exc
        raise HTTPException(
            status_code=502, detail=memory_cards.CARD_IMPORT_FAILED_DETAIL
        ) from exc

    if content is None and card_import == "adopt":
        # The slot is empty now, so the import the user asked for cannot
        # happen. Abort without recording so the prompt fires again.
        log.warning("adopt requested but the container slot is empty")
        await lifecycle.abort_claim(container.key, session)
        raise HTTPException(
            status_code=502, detail=memory_cards.CARD_IMPORT_FAILED_DETAIL
        )
    if content is not None and card_import is None:
        await lifecycle.abort_claim(container.key, session)
        raise HTTPException(
            status_code=428,
            detail=MemoryCardImportRequired(
                code="memory_card_import_required",
                outcome="found",
                summary=MemoryCardSummarySchema(**memory_cards.summarize_card(content)),
            ).model_dump(),
        )
    return _ContainerCard(
        undecided=True, content=None if card_import == "discard" else content
    )


async def _settle_memory_card(
    request: Request,
    container: ResolvedContainer,
    session: dict[str, Any],
    card: MemoryCard | None,
    rom: Rom,
    probe: _ContainerCard,
) -> tuple[MemoryCard | None, int | None]:
    """The card this session mounts, plus the id of a blank the claim created.

    Returns (card, blank id). The blank is made only now, so a lost race (409)
    never leaves an orphan card behind; if a later step aborts the claim, that
    id is what deletes it again.
    """
    if not container.memory_card_sync:
        return card, None

    created_blank_card_id: int | None = None
    if card is None:
        card = memory_cards.create_blank_card(
            request.user.id, container.emulator, rom.platform_id
        )
        created_blank_card_id = card.id
        session["memory_card_id"] = card.id
        # Through mutate_session, not a plain SET: a force-release landing in
        # this window deletes the key, and writing it back whole would resurrect
        # a claim on a container whose emulator is already being stopped.
        try:
            await mutate_session(container.key, {"memory_card_id": card.id})
        except StreamingSessionContended:
            log.warning(
                "could not record card %s on session %s", card.id, container.key
            )

    if not probe.undecided:
        return card, created_blank_card_id

    # Establish version 1 from the container's own card before hydrate runs, so
    # the hydrate that follows pushes the adopted card back rather than a blank.
    # An absent or discarded card is recorded too, so the prompt fires once and
    # a card that shows up later is treated as the container's, not the user's.
    if probe.content is not None:
        stored: MemoryCardVersion | None = None
        try:
            stored = await memory_cards.store_memory_card_version(
                request.user, card, probe.content
            )
        except Exception as exc:
            # Hydrate would wipe the container next, so a failed import must
            # abort rather than destroy the card it was asked to keep.
            log.exception("could not adopt the container memory card")
            await lifecycle.abort_claim(container.key, session, created_blank_card_id)
            raise HTTPException(
                status_code=502, detail=memory_cards.CARD_IMPORT_FAILED_DETAIL
            ) from exc
        if not stored and not memory_cards.adoption_already_stored(
            card.id, probe.content
        ):
            # Content-hash dedup matched an older version of this card, so no
            # version was created and hydrate would push whichever version is
            # latest over the container card. Abort instead.
            log.error(
                "adopted memory card matched an existing version of card %d", card.id
            )
            await lifecycle.abort_claim(container.key, session, created_blank_card_id)
            raise HTTPException(
                status_code=502, detail=memory_cards.CARD_IMPORT_FAILED_DETAIL
            )

    db_container_adoption_handler.add_adoption(
        container_key=container.key,
        outcome="adopt" if probe.content is not None else "discard",
        user_id=request.user.id,
    )
    return card, created_blank_card_id


async def _hydrate_saves(
    request: Request,
    container: ResolvedContainer,
    session: dict[str, Any],
    rom: Rom,
    card: MemoryCard | None,
    blank_card_id: int | None,
) -> str | None:
    """Put the player's save data on the container before the game reads it.

    Games read saves at boot, so unlike states this cannot be deferred to a
    background task. Returns the container path of an uploaded archive, for the
    protocols that restore one as part of the launch.
    """
    if card is not None:
        # Whole-card sync: hydrate (or wipe to blank) is REQUIRED. If it fails
        # we cannot guarantee the container is isolated from the previous
        # player's card, so abort the claim rather than launch a leaky session.
        try:
            hydrated = await memory_cards.hydrate_card_to_broker(
                request.user.id, card, container
            )
        except Exception:
            log.exception("memory card hydration failed")
            hydrated = False
        if not hydrated:
            await lifecycle.abort_claim(container.key, session, blank_card_id)
            raise HTTPException(
                status_code=502, detail="Could not prepare the memory card"
            )

    if container.is_webstation:
        # Restore runs inside activate on this protocol, so hydration only gets
        # the bytes onto the container and names the path activate restores.
        # Still runs under whole-card sync: the archive carries the state the
        # last session ended on, which the card does not.
        # Best-effort: a failed upload just means the container keeps its own.
        try:
            return await saves.hydrate_saves_to_webstation(
                request.user.id, rom.id, container
            )
        except Exception:
            log.exception("save hydration failed, continuing launch")
    elif card is None:
        # Legacy per-file save sync (containers without memory_card_sync).
        # Best-effort: a failed hydration just means the container keeps its own.
        try:
            await saves.hydrate_saves_to_broker(request.user.id, rom.id, container)
        except Exception:
            log.exception("save hydration failed, continuing launch")
    return None


@protected_route(
    router.post,
    "/sessions",
    [Scope.ROMS_USER_WRITE],
    # The prompt for a card the container still holds is a real body the client
    # parses, so it is declared rather than left as an undocumented `detail`.
    responses={428: {"model": MemoryCardImportRequired}},
    status_code=202,
)
async def claim_session(
    request: Request,
    req: Annotated[ClaimStreamingSessionRequest, Body()],
    background_tasks: BackgroundTasks,
) -> LaunchingSessionSchema:
    """
    Reserve a container for a ROM and start loading it.

    Answers 202 as soon as the container is reserved and everything that can
    fail synchronously has: the launch itself runs detached, and the room URL
    arrives over the socket as `streaming:launch-ready` (or
    `streaming:launch-failed`, with `streaming:launch-phase` while a broker
    unpacks a large title). `GET /sessions/{platform}/status` is the fallback
    for a tab that missed the push.

    The ROM's filesystem path is derived server-side from its database row -
    the client only supplies a ROM id, never a path.
    Returns 404 if the ROM doesn't exist or no container serves its platform.
    Returns 409 if every container serving the platform is occupied.
    Returns 428 if the container's pre-existing memory card needs a decision.
    """
    rom = db_rom_handler.get_rom(req.rom_id)
    if rom is None:
        raise HTTPException(status_code=404, detail="ROM not found")

    # A hidden ROM/platform must not be launchable via its id: enforce the same
    # visibility policy as the ROM detail/content endpoints before any broker
    # launch. Raises a 404 that masks the hidden ROM's existence.
    assert_rom_visible(request, rom, not_found_detail="ROM not found")

    platform = rom.platform_slug
    candidates = containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )

    # Pool members are interchangeable on emulator and card sync (enforced by
    # containers_for_platform), so the pre-claim validation below holds for
    # whichever one the walk ends up winning.
    reference = candidates[0]

    # Validate the resume pick before claiming so a bad state_id cannot
    # leave a container wedged behind a failed launch.
    resume_state = None
    resume_slot: int | None = None
    if req.state_id is not None:
        resume_state, resume_slot = states.resolve_resume_state(
            request.user.id, rom, reference, req.state_id
        )

    # Resolve the memory card to mount before claiming too, so a bad card id
    # fails cleanly (whole-card-sync containers only). May be None on first
    # play; the blank card is created only after the claim is won.
    memory_card = None
    if reference.memory_card_sync:
        memory_card = memory_cards.resolve_card(
            request.user.id,
            reference.emulator,
            req.memory_card_id,
        )

    # A broker with no join route cannot seat a second viewer, so recording
    # the flag there would advertise a session every Join would 409 on.
    multiplayer = req.multiplayer and reference.protocol.supports_join

    rom_name = rom.name or rom.fs_name_no_ext
    # A launcher whose games ship several languages in one folder (ScummVM
    # detects one target per language) picks the variant that boots from these.
    # RomM rarely knows a game's own language, and a multilingual folder is
    # exactly the case where it usually does not, so the player's interface
    # locale travels with it as the broker's fallback.
    rom_language = languages.rom_language(rom)
    gui_language = languages.gui_language(request.user)

    now = datetime.now(timezone.utc).isoformat()
    session = {
        # Unique per claim, and safe to put in a filename. The webstation
        # broker names its exit archive after it, so the pull can tell this
        # session's saves from one an earlier pull failed to collect.
        "broker_session_id": secrets.token_hex(8),
        "rom_id": rom.id,
        "rom_name": rom_name,
        # Stored so admin views can release through the platform-keyed DELETE
        # route without reverse-mapping the container key, and so a container
        # serving several platforms resolves back to the right config entry.
        "platform": platform,
        "claimed_at": now,
        # Liveness stamp, refreshed by the heartbeat endpoint. A session that
        # stops refreshing counts as abandoned and can be taken over.
        "last_seen": now,
        "user_id": request.user.id,
        # Read by GET /sessions/joinable and enforced by POST
        # /sessions/{platform}/join, so it has to survive on the record rather
        # than living only on the broker.
        "multiplayer": multiplayer,
        # Carried so every teardown path (owner release, save-and-exit, admin
        # force-release) can evacuate the right card before stopping the game.
        "memory_card_id": memory_card.id if memory_card is not None else None,
    }

    container = await _win_container(request, candidates, session, platform)
    session_key = container.key

    # The emulator containers mount the RomM library at the same path the
    # backend uses (LIBRARY_BASE_PATH, /romm/library by default), so the
    # backend-side path is valid inside the broker container too. If a
    # container mounts the library at a different path, `library_path` on
    # its config entry overrides the prefix so the broker receives a path
    # that is valid inside that container.
    library_base = container.library_path
    rom_path = f"{library_base}/{rom.full_path}"

    probe = await _probe_container_card(container, session, req.card_import)

    # The player is back in a session, so any note about their previous one
    # being force-released has served its purpose. Cleared across the whole
    # pool, not just the container just won: the notice is keyed by container,
    # and one left on a sibling would be reported as the reason this session
    # ended when it finally does.
    for candidate in candidates:
        await clear_termination(candidate.key, request.user.id)

    memory_card, created_blank_card_id = await _settle_memory_card(
        request, container, session, memory_card, rom, probe
    )

    # Push the resume state before launch so its file is in place when the
    # broker's deferred slot load fires. Best-effort: a failed push falls
    # back to a fresh launch, reported through `resume` in the response.
    # The webstation broker only takes a state while a session is up, and its
    # session starts at activate, so that push has to happen after launch.
    resume_pushed = False
    resume_after_launch = container.is_webstation and resume_state is not None
    if resume_state is not None and not resume_after_launch:
        resume_pushed = await states.push_resume_state(container, resume_state)

    archive_path = await _hydrate_saves(
        request, container, session, rom, memory_card, created_blank_card_id
    )

    # Detached because an activate blocks through pkg and archive extraction,
    # minutes on a large title, which no player can cancel out of.
    background_tasks.add_task(
        launch.run_launch,
        container=container,
        session_key=session_key,
        session=session,
        user=request.user,
        rom=rom,
        platform=platform,
        rom_name=rom_name,
        rom_path=rom_path,
        rom_language=rom_language,
        gui_language=gui_language,
        archive_path=archive_path,
        resume_state=resume_state,
        resume_slot=resume_slot,
        resume_pushed=resume_pushed,
        resume_after_launch=resume_after_launch,
        memory_card_synced=memory_card is not None,
        multiplayer=multiplayer,
        blank_card_id=created_blank_card_id,
    )

    return LaunchingSessionSchema(
        platform=platform,
        container=session_key,
        label=container.label,
        rom_name=rom_name,
        claimed_at=now,
    )


@protected_route(
    router.post, "/sessions/{platform}/save-and-exit", [Scope.ROMS_USER_WRITE]
)
async def save_and_exit_session(
    request: Request, platform: str, req: Annotated[SaveAndExitRequest, Body()]
) -> SaveAndExitResponse:
    """
    Save game state then release the session.
    wait=true (default): blocks until broker confirms save+kill complete.
    wait=false: broker fires save+kill in background, returns immediately.
    """
    container, session_key, session = await access.resolve_owned_session(
        platform, request
    )
    if req.slot:
        _assert_valid_slot(platform, req.slot)

    # Whole-card sync must evacuate a quiescent card, so force a blocking
    # save+kill for these containers even on the navigate-away (wait=false)
    # path. Otherwise the evacuate below can read a card the emulator is
    # still writing, and the wipe can race its exit flush.
    card_sync = container.memory_card_sync
    effective_wait = True if card_sync else req.wait
    saved, effective_slot = await asyncio.to_thread(
        commands.save_and_exit, container, slot=req.slot, wait=effective_wait
    )

    # Evacuate the whole card while the claim still guards the container, so a
    # concurrent claim cannot wipe it first. The save+kill above was blocking
    # on the card-sync path, so the game is stopped and the card is quiescent.
    # Awaited before the key is released.
    safe_to_wipe = await memory_cards.evacuate_session_card(session, container)
    if safe_to_wipe:
        await memory_cards.wipe_session_card(container)

    await lifecycle.record_play_session(session)
    await lifecycle.clear_session_activity(session_key, session)

    # Sync the exit save to the library. With wait=false the broker save may
    # still be running; the pull blocks on the broker until it finishes.
    rom_id = session.get("rom_id")
    pull_state = (
        states.pull_state_to_library(
            access.session_owner_id(session, request),
            rom_id,
            container,
            effective_slot,
            disc_file_id=session_disc_id(session),
        )
        if isinstance(rom_id, int) and (saved or not effective_wait)
        else None
    )

    released = True
    if pull_state is not None:
        # The container holds until the state is in the library. The broker keeps
        # the exited session's state only until the next activate, so dropping
        # the key first is what lets a new claim overwrite it.
        try:
            token = await claim_drain_marker(session_key, session)
        except StreamingSessionContended:
            background.spawn_sync_task(
                lifecycle.release_after_state_pull(
                    session_key, pull_state, None, session
                )
            )
        else:
            if token is None:
                # The key stopped being this claim while the save+kill blocked,
                # so the pull runs without holding anything: whoever owns the
                # container now owns the key too.
                pull_state.close()
                log.warning(
                    "skipping the exit state pull, session %s was taken over",
                    session_key,
                )
            else:
                background.spawn_sync_task(
                    lifecycle.release_after_state_pull(
                        session_key, pull_state, token, session
                    )
                )
    elif effective_wait:
        # Broker confirmed the save+kill is done and there is no state coming
        # back, the key can go now.
        released = await release_own_session(session_key, session)
    else:
        # Broker is still killing the emulator in the background. Drop the
        # key to a short drain TTL instead of deleting it outright: a
        # concurrent new claim is briefly blocked so it can't /launch on
        # top of a not-yet-dead emulator (which would lose the in-flight
        # save). The marker is JSON so get_session leaves it in place
        # (a bare string would parse as corrupt and be deleted, ending
        # the drain early). The key expires on its own once the window passes.
        try:
            await claim_drain_marker(
                session_key, session, STREAMING_SESSION_DRAIN_SECONDS
            )
        except StreamingSessionContended:
            released = False

    lifecycle.collect_exit_saves(container, session)

    if not released:
        log.error("save-and-exit could not give up session %s", session_key)
    log.info("save-and-exit, platform=%s saved=%s", platform, saved)
    # `released` false means the container is still on this claim, so the client
    # is still the one holding it and has to try again.
    return SaveAndExitResponse(
        status="ok", saved=saved, platform=platform, released=released
    )


@protected_route(router.post, "/sessions/{platform}/heartbeat", [Scope.ROMS_USER_WRITE])
async def heartbeat_session(request: Request, platform: str) -> SessionStatusSchema:
    """Refresh the session's liveness stamp and report whether it still exists.

    The frontend calls this every ~30s while a session is active. A session
    that stops refreshing counts as abandoned after _STREAMING_SESSION_STALE_SECONDS
    and the next claim may take the container over.

    Reports `ended` rather than raising 404 when the caller no longer holds the
    session, so a force-released player learns why on the poll they are already
    making rather than watching a dead stream.
    """
    candidates = containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )
    found = await access.find_session_for_user(candidates, request.user.id)
    if found is None:
        return SessionStatusSchema(**await _session_status(platform, request))
    _, session_key, _ = found

    # Merging rather than writing the copy read above keeps a swap that landed
    # in between; refusing a draining session keeps a heartbeat from making a
    # container that is already being torn down look live. Either returns None,
    # meaning the claim is gone and reporting "active" would leave the client
    # beating a session it no longer holds.
    try:
        refreshed = await mutate_session(
            session_key,
            {"last_seen": datetime.now(timezone.utc).isoformat()},
            require=lambda s: not s.get("draining"),
        )
    except StreamingSessionContended:
        # A key too busy to write is a key that exists, so the session is live
        # and the missed stamp is covered by the next beat.
        log.warning("heartbeat could not stamp contended session %s", session_key)
        return SessionStatusSchema(status="active", platform=platform)
    if refreshed is None:
        return SessionStatusSchema(**await _session_status(platform, request))
    await lifecycle.refresh_session_activity(session_key, refreshed)
    return SessionStatusSchema(status="active", platform=platform)


@protected_route(router.get, "/sessions/{platform}/status", [Scope.ROMS_READ])
async def session_status(request: Request, platform: str) -> SessionStatusSchema:
    """Does the caller still hold this platform's session?

    Unlike the heartbeat this has no side effects, so a client can call it on
    mount or after a reconnect without extending a claim it may not own.
    """
    return SessionStatusSchema(**await _session_status(platform, request))


@protected_route(router.post, "/sessions/{platform}/join", [Scope.ROMS_READ])
async def join_session(
    request: Request,
    platform: str,
    container: str | None = Query(default=None),
) -> JoinedSessionSchema:
    """Join a multiplayer session someone else is hosting.

    The caller gets a room URL and nothing else. Note the scope: ROMS_READ,
    not the ROMS_USER_WRITE every control route below demands. Those all go
    through access.assert_session_owner, so a joiner cannot change the volume, write
    states, or release the container.
    """
    if container is not None:
        candidate, _, session = await access.resolve_named_container(
            platform, container
        )
        found = (candidate, session) if session is not None else None
    else:
        found = None
        for candidate in containers_for_platform(platform):
            session = await get_live_session(candidate.key)
            if session is None:
                continue
            if session.get("multiplayer"):
                found = (candidate, session)
                break

    if found is None:
        raise HTTPException(
            status_code=404, detail=f"No active session on platform '{platform}'"
        )
    candidate, session = found

    if not session.get("multiplayer"):
        raise HTTPException(
            status_code=403, detail="That session is not open for joining"
        )

    # Joining streams someone else's ROM, so it needs the same visibility
    # policy the claim route enforces. Masked as the not-found above so a
    # hidden ROM's existence stays hidden.
    access.assert_session_rom_visible(
        request, session, not_found_detail=f"No active session on platform '{platform}'"
    )

    if not candidate.protocol.supports_join:
        raise HTTPException(
            status_code=409, detail="That container does not support joining"
        )

    joined = await asyncio.to_thread(webstation.join, candidate, request.user)
    room_url = str(joined.get("url", "")) if joined else ""
    if not room_url:
        raise HTTPException(status_code=502, detail="The session refused the join")

    return JoinedSessionSchema(
        platform=platform,
        host=room_url_on(candidate.host, room_url),
        label=candidate.label,
        rom_id=session.get("rom_id"),
        rom_name=session.get("rom_name"),
    )


@protected_route(router.post, "/sessions/{platform}/volume", [Scope.ROMS_USER_WRITE])
async def set_volume(
    request: Request, platform: str, req: Annotated[VolumeRequest, Body()]
) -> VolumeResponse:
    """Set emulator audio volume (0-100)."""
    container, session_key, _ = await access.resolve_owned_session(platform, request)

    ok = await asyncio.to_thread(commands.set_volume, container, req.level)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to set volume")

    await refresh_session(session_key)
    return VolumeResponse(status="ok", level=req.level, platform=platform)


@protected_route(router.post, "/sessions/{platform}/mute", [Scope.ROMS_USER_WRITE])
async def set_mute(
    request: Request, platform: str, req: Annotated[MuteRequest, Body()]
) -> MuteResponse:
    """Toggle or explicitly set mute state. Omit body to toggle."""
    container, session_key, _ = await access.resolve_owned_session(platform, request)

    confirmed = await asyncio.to_thread(commands.set_mute, container, req.mute)
    if confirmed is None:
        raise HTTPException(status_code=502, detail="Broker failed to set mute state")

    await refresh_session(session_key)
    return MuteResponse(status="ok", mute=confirmed, platform=platform)


@protected_route(
    router.post, "/sessions/{platform}/save-state", [Scope.ROMS_USER_WRITE]
)
async def save_state(
    request: Request, platform: str, req: Annotated[SaveStateRequest, Body()]
) -> SaveStateResponse:
    """Save game state to a slot without stopping the emulator.

    The autosave slot is a valid target: the library keeps every capture, so
    the player writes through one slot rather than picking one.
    """
    container, session_key, session = await access.resolve_owned_session(
        platform, request
    )
    _assert_valid_slot(platform, req.slot)

    ok = await asyncio.to_thread(commands.save_state, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to save state")

    await refresh_session(session_key)

    # Every save syncs to the library in the background. The broker holds the
    # /state-file response until the emulator finishes writing the slot.
    rom_id = session.get("rom_id")
    if isinstance(rom_id, int):
        background.spawn_sync_task(
            states.pull_state_to_library(
                access.session_owner_id(session, request),
                rom_id,
                container,
                req.slot,
                disc_file_id=session_disc_id(session),
            )
        )

    return SaveStateResponse(status="saving", slot=req.slot, platform=platform)


@protected_route(
    router.post, "/sessions/{platform}/state-frame", [Scope.ROMS_USER_WRITE]
)
async def put_state_frame(request: Request, platform: str) -> StateFrameResponse:
    """Stash a frame the browser grabbed off the stream canvas, for the state
    save that follows it to pick up as its thumbnail."""
    _, session_key, session = await access.resolve_owned_session(platform, request)

    image = await _read_capped_body(request, states.SCREENSHOT_MAX_BYTES)
    if image is None:
        raise HTTPException(status_code=413, detail="Frame too large")
    if not image.startswith(states.PNG_MAGIC):
        raise HTTPException(status_code=400, detail="Frame must be a PNG")

    rom_id = session.get("rom_id")
    if not isinstance(rom_id, int):
        raise HTTPException(status_code=409, detail="Session has no rom")

    await states.stash_state_frame(
        access.session_owner_id(session, request), rom_id, image
    )
    await refresh_session(session_key)
    return StateFrameResponse(status="ok", platform=platform)


@protected_route(
    router.post, "/sessions/{platform}/load-state", [Scope.ROMS_USER_WRITE]
)
async def load_state(
    request: Request, platform: str, req: Annotated[LoadStateRequest, Body()]
) -> LoadStateResponse:
    """Load game state from a manual slot or the platform's autosave slot."""
    container, session_key, _ = await access.resolve_owned_session(platform, request)
    _assert_valid_slot(platform, req.slot)

    ok = await asyncio.to_thread(commands.load_state, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to load state")

    await refresh_session(session_key)
    return LoadStateResponse(status="ok", loaded=True, slot=req.slot, platform=platform)


@protected_route(router.post, "/sessions/{platform}/swap-disc", [Scope.ROMS_USER_WRITE])
async def swap_disc(
    request: Request, platform: str, req: Annotated[SwapDiscRequest, Body()]
) -> SwapDiscResponse:
    """Change the mounted disc without restarting the emulator."""
    container, session_key, session = await access.resolve_owned_session(
        platform, request
    )
    # Container-scoped, not platform-scoped: only the webstation broker has a
    # tray route, so a legacy container serving this platform gets the same
    # refusal the frontend was told to expect rather than a 502 from the broker.
    if not container.capabilities["supports_disc_swap"]:
        raise HTTPException(
            status_code=400, detail=f"Platform '{platform}' cannot swap discs"
        )

    rom_id = session.get("rom_id")
    if not isinstance(rom_id, int):
        raise HTTPException(status_code=409, detail="Session has no rom")
    rom_file = db_rom_handler.get_rom_file_by_id(req.file_id)
    if rom_file is None or rom_file.rom_id != rom_id:
        raise HTTPException(status_code=404, detail="File does not belong to this rom")

    # Loaded separately: the file comes back detached, so reaching its rom from
    # there is a lazy load with no session behind it.
    rom = db_rom_handler.get_rom(rom_id)
    if rom is None:
        raise HTTPException(status_code=404, detail="Rom not found")

    if req.file_id not in _swappable_disc_file_ids(rom):
        raise HTTPException(status_code=400, detail="File is not a swappable disc")

    library_base = container.library_path
    disc_path = f"{library_base}/{rom_file.full_path}"
    ok = await asyncio.to_thread(commands.swap_disc, container, disc_path)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to swap disc")

    # Resets the TTL as part of the same write.
    await set_session_disc(session_key, req.file_id, session.get("broker_session_id"))
    return SwapDiscResponse(status="ok", file_id=req.file_id, platform=platform)


@protected_route(router.delete, "/sessions/{platform}", [Scope.ROMS_USER_WRITE])
async def release_session(
    request: Request,
    platform: str,
    background_tasks: BackgroundTasks,
    reason: str | None = Query(default=None, max_length=200),
    container_key: str | None = Query(default=None, alias="container", max_length=300),
    save: bool = Query(default=True),
) -> ReleaseSessionResponse:
    """Release a session and tell the broker to stop the emulator.

    `reason` is only meaningful when an admin ends someone else's session; it
    is surfaced to the displaced player. `container` names which container to
    release, needed when a pool serves the platform and the admin is ending a
    session they do not own; it is the key `GET /streaming/sessions` reports.

    `save=false` is a player leaving deliberately without saving. It defaults
    on because the other way in here is a tab closing, where nobody chose
    anything and the last minutes of play would otherwise be gone.
    """
    if container_key is not None:
        container, session_key, session = await access.resolve_named_container(
            platform, container_key
        )
        if session is None:
            return ReleaseSessionResponse(status="not_found", platform=platform)
        access.assert_session_owner(session, request)
    else:
        try:
            container, session_key, session = await access.resolve_owned_session(
                platform, request
            )
        except HTTPException as exc:
            # Nothing configured or nothing active: releasing is a no-op rather
            # than an error, matching a repeated release from the same tab.
            if exc.status_code != 404:
                raise
            return ReleaseSessionResponse(status="not_found", platform=platform)

    # Teardown pulls the whole card off the broker and pushes a blank one back,
    # several seconds of broker round-trips. The player who quit does not need
    # the claim released to get their UI back, so it runs after the response is
    # sent. The Redis claim stays held until teardown deletes it, so a re-launch
    # or concurrent claim is still blocked throughout, preserving the
    # evacuate-before-release invariant.
    background_tasks.add_task(
        lifecycle.teardown_released_session,
        container,
        session,
        session_key,
        platform,
        acting_user_id=request.user.id,
        acting_username=request.user.username,
        reason=reason,
        save=save,
    )
    log.info("session releasing, platform=%s save=%s", platform, save)
    return ReleaseSessionResponse(status="released", platform=platform)


@protected_route(router.get, "/containers", [Scope.ROMS_READ])
async def list_containers(request: Request) -> AdminContainersResponse:
    """Admin view, one row per configured container with whatever it is running.

    One row per container rather than per platform: a container serves many
    platforms but hosts one session, so the platform rows the frontend gets
    from `/streaming/config` are the wrong unit for operating the fleet.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    containers: list[dict[str, Any]] = []
    for container_key, entries in containers_by_key().items():
        first = entries[0]
        session = await get_live_session(container_key) if container_key else None
        user_id = session.get("user_id") if session else None
        user = db_user_handler.get_user(user_id) if isinstance(user_id, int) else None
        containers.append(
            {
                "container": container_key,
                "label": first.container_label or first.label,
                "host": first.host,
                "platforms": [e.platform for e in entries],
                "supports_desktop": first.protocol.supports_desktop,
                # A container whose host has no scheme has an empty key and can
                # never be claimed, so surface it rather than listing it as idle.
                "configured": bool(container_key),
                "session": (
                    {
                        "platform": session.get("platform"),
                        "rom_id": session.get("rom_id"),
                        "rom_name": session.get("rom_name"),
                        "desktop": bool(session.get("desktop")),
                        "claimed_at": session.get("claimed_at"),
                        "user_id": user_id,
                        "username": user.username if user else None,
                    }
                    if session
                    else None
                ),
            }
        )
    return AdminContainersResponse(enabled=streaming_enabled(), containers=containers)


@protected_route(router.post, "/desktop", [Scope.ROMS_USER_WRITE])
async def claim_desktop_session(
    request: Request, req: Annotated[DesktopStreamingSessionRequest, Body()]
) -> DesktopSessionSchema:
    """Admin, open a container's desktop with no game running.

    This is how an operator configures an emulator (BIOS, controllers, paths)
    inside the container that will run it. The desktop claims the same key
    under the same SET NX as a game, so it blocks players and a running game
    blocks it: only one thing can drive the container's display.

    Returns 404 for an unknown container, 409 when it is occupied, 502/503 when
    the broker rejects the activation or is unreachable.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    container, platform = access.container_by_key(req.container)
    if not container.protocol.supports_desktop:
        raise HTTPException(
            status_code=400,
            detail="This container's broker does not serve a desktop session",
        )

    session_key = container.key
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "user_id": request.user.id,
        "broker_session_id": secrets.token_hex(8),
        # No ROM and no card. Teardown reads both and skips the save pull, the
        # card evacuation and the playtime credit when they are absent, which
        # is what a desktop session wants: nothing of it belongs in a library.
        "rom_id": None,
        "rom_name": None,
        "memory_card_id": None,
        "desktop": True,
        "platform": platform,
        "claimed_at": now,
        "last_seen": now,
    }
    # No stale takeover here, unlike a player's claim: the admin named this
    # container, so displacing whoever holds it should be their explicit call
    # through release, not a side effect of asking for the desktop.
    claimed = await async_cache.set(
        session_redis_key(session_key),
        json.dumps(session),
        nx=True,
        ex=STREAMING_SESSION_TTL_SECONDS,
    )
    if not claimed:
        existing = await get_session(session_key) or {}
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Container in use",
                "rom_name": access.visible_rom_name(request, existing),
                "claimed_at": existing.get("claimed_at"),
            },
        )

    try:
        launch_result = await asyncio.to_thread(
            webstation.activate,
            container,
            session_id=str(session["broker_session_id"]),
            user=request.user,
            emulator="desktop",
            gui_language=languages.gui_language(request.user),
        )
    except Exception:
        # Activation failed, free the claim so the container isn't wedged.
        await lifecycle.abort_claim(session_key, session)
        raise

    room_url = str(launch_result.get("url", "")) if launch_result else ""
    host = room_url_on(container.host, room_url)

    await stamp_launched(session_key, session)
    log.info("desktop session claimed, container=%s", session_key)
    return DesktopSessionSchema(
        container=session_key,
        platform=platform,
        host=host,
        label=container.label,
        claimed_at=now,
    )


@protected_route(router.get, "/sessions/joinable", [Scope.ROMS_READ])
async def list_joinable_sessions(
    request: Request, rom_id: int | None = Query(default=None, ge=1)
) -> JoinableSessionsResponse:
    """Active multiplayer sessions any user may ask to join.

    Deliberately not admin-gated, unlike GET /sessions: it exposes only
    sessions whose host opted into multiplayer at launch, and only the fields
    a Join button needs. Sessions the caller is already hosting are left out.
    """
    grouped = containers_by_key()

    sessions: list[dict[str, Any]] = []
    async for container_key, s in iter_live_sessions():
        if not s.get("multiplayer"):
            continue
        if s.get("user_id") == request.user.id:
            continue
        if rom_id is not None and s.get("rom_id") != rom_id:
            continue
        session_rom_id = s.get("rom_id")
        rom = (
            db_rom_handler.get_rom_simple(session_rom_id)
            if session_rom_id is not None
            else None
        )
        if not access.rom_is_visible(request, rom):
            continue

        user_id = s.get("user_id")
        host = db_user_handler.get_user(user_id) if user_id is not None else None
        sessions.append(
            {
                "container": container_key,
                "label": _joinable_container_label(grouped, container_key),
                "platform": s.get("platform"),
                "rom_id": session_rom_id,
                "rom_name": s.get("rom_name"),
                "host_username": host.username if host else None,
                "claimed_at": s.get("claimed_at"),
                # Enough of the ROM to draw a cover tile without a second
                # request per session.
                "platform_id": rom.platform_id if rom else None,
                "platform_display_name": rom.platform_display_name if rom else None,
                "path_cover_small": rom.path_cover_small if rom else None,
                "path_cover_large": rom.path_cover_large if rom else None,
                "url_cover": rom.url_cover if rom else None,
            }
        )
    return JoinableSessionsResponse(sessions=sessions)


@protected_route(router.get, "/sessions", [Scope.ROMS_READ])
async def list_sessions(request: Request) -> AdminSessionsResponse:
    """Admin view, active sessions across all configured containers.

    Entries carry the platform the session was claimed under so an admin
    client can release one through `DELETE /sessions/{platform}`.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    grouped = containers_by_key()

    sessions: list[dict[str, Any]] = []
    async for container_key, s in iter_live_sessions():
        container = container_for_session(grouped, container_key, s.get("platform"))
        user_id = s.get("user_id")
        user = db_user_handler.get_user(user_id) if user_id is not None else None
        sessions.append(
            {
                "container": container_key,
                "label": container.label if container else None,
                "platform": s.get("platform"),
                "rom_id": s.get("rom_id"),
                "rom_name": s.get("rom_name"),
                "desktop": bool(s.get("desktop")),
                "claimed_at": s.get("claimed_at"),
                "user_id": user_id,
                "username": user.username if user else None,
            }
        )
    return AdminSessionsResponse(sessions=sessions)


@protected_route(router.delete, "/sessions", [Scope.ROMS_USER_WRITE])
async def force_release_all(
    request: Request, reason: str | None = Query(default=None, max_length=200)
) -> ForceReleaseResponse:
    """Admin, force-release all active sessions.

    `reason` is surfaced to every displaced player alongside the admin's name.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Map container keys back to configs so each broker can be told to stop -
    # deleting only the Redis keys would leave the games running.
    grouped = containers_by_key()

    async def _teardown(key: str | bytes, container_key: str) -> None:
        # Read before the teardown so the displaced player can be identified
        # even when the container config has since been removed.
        session = await get_session(container_key)
        container = container_for_session(
            grouped, container_key, session.get("platform") if session else None
        )

        # All of it runs while the claim still guards the container and before
        # the key is deleted.
        try:
            if container is not None:
                # Best-effort; a broker error must not abort the sweep.
                if session is None:
                    # The row went between the scan and the read; stop the
                    # emulator anyway rather than leave it running.
                    await asyncio.to_thread(commands.stop, container)
                else:
                    state_slot = await lifecycle.quiesce_container(container, session)
                    # Credit playtime to the session's owner, not the admin.
                    await lifecycle.record_play_session(session)
                    await lifecycle.clear_session_activity(container_key, session)
                    await lifecycle.collect_exit_state(container, session, state_slot)
                    lifecycle.collect_exit_saves(container, session)

            # Note who ended it before the key goes, so the player's next poll
            # can explain the stream vanishing.
            if session is not None:
                await record_termination(
                    session,
                    container_key,
                    ended_by=request.user.username,
                    reason=reason,
                )
        finally:
            # The sweep answered "released", so the key goes even when a step
            # above raised; a phantom claim would block every later claim.
            await async_cache.delete(key)

    released = []
    teardowns = []
    async for container_key in iter_session_keys():
        # A drain marker is a teardown already running: it hands the container
        # back once the exit state is out of it, and cutting that short would
        # lose the state and free the container mid-pull.
        marker = await get_session(container_key)
        if marker is not None and marker.get("draining"):
            continue
        released.append(container_key)
        teardowns.append(_teardown(session_redis_key(container_key), container_key))

    # Tear down concurrently so one slow or stuck broker cannot serialize the
    # whole sweep behind its timeout.
    results = await asyncio.gather(*teardowns, return_exceptions=True)
    for container_key, result in zip(released, results, strict=False):
        if isinstance(result, BaseException):
            log.warning("force-release failed for %s, %s", container_key, result)

    log.info("all sessions force-released by admin, %s", released)
    return ForceReleaseResponse(status="released", platforms=released)
