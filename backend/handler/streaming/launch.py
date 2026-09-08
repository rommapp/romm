"""Starting a game on a container the claim already won.

Detached from the request that asked for it: an activate blocks through pkg
and archive extraction, minutes on a large title, so the room URL and the
progress behind it reach the player over the socket instead.
"""

import asyncio
from typing import Any

from fastapi import HTTPException

from endpoints.responses.streaming import (
    LaunchFailedPayload,
    LaunchPhasePayload,
    LaunchReadyPayload,
)
from handler.streaming import background, commands, lifecycle, states, webstation
from handler.streaming.config import ResolvedContainer
from handler.streaming.session_store import (
    hold_session_claim,
    push_to_user,
    stamp_launched,
)
from logger.logger import log
from models.assets import State
from models.rom import Rom
from models.user import User


async def run_launch(
    *,
    container: ResolvedContainer,
    session_key: str,
    session: dict[str, Any],
    user: User,
    rom: Rom,
    platform: str,
    rom_name: str,
    rom_path: str,
    rom_language: str | None,
    gui_language: str | None,
    archive_path: str | None,
    resume_state: State | None,
    resume_slot: int | None,
    resume_pushed: bool,
    resume_after_launch: bool,
    memory_card_synced: bool,
    multiplayer: bool,
    blank_card_id: int | None,
) -> None:
    """Start the game, then tell the player's tabs where to find it.

    The claim is already won, so the container stays reserved throughout and a
    failure here is what frees it again.
    """
    # Nothing beats for the player until the stream is up, so without this the
    # next claimant reads the record as abandoned and tears the container down
    # mid-extraction.
    claim_hold = asyncio.create_task(hold_session_claim(session_key, session))
    phase_watch = asyncio.create_task(
        _watch_launch_phase(container, session_key, session, platform)
    )
    try:
        # Wrapped in asyncio.to_thread because urllib is synchronous.
        if container.is_webstation:
            launch_result = await asyncio.to_thread(
                webstation.activate,
                container,
                session_id=str(session["broker_session_id"]),
                user=user,
                emulator=container.emulator,
                rom={
                    "id": rom.id,
                    "name": rom_name,
                    "platform": platform,
                    "language": rom_language,
                    "path": rom_path,
                },
                gui_language=gui_language,
                archive_path=archive_path,
                resume_slot=(
                    resume_slot if resume_pushed or resume_after_launch else None
                ),
                memory_card_synced=memory_card_synced,
                multiplayer=multiplayer,
            )
        else:
            launch_result = await asyncio.to_thread(
                commands.launch,
                container,
                rom_path,
                rom_name,
                resume_slot if resume_pushed else None,
            )
    except Exception as exc:
        log.exception("launch failed, platform=%s", platform)
        await lifecycle.abort_claim(session_key, session, blank_card_id)
        await push_to_user(
            session.get("user_id"),
            "streaming:launch-failed",
            LaunchFailedPayload(
                platform=platform,
                container=session_key,
                detail=_failure_detail(exc),
            ).model_dump(),
        )
        return
    finally:
        phase_watch.cancel()
        claim_hold.cancel()

    log.info("session claimed, platform=%s rom=%s", platform, rom_name)
    await stamp_launched(session_key, session)
    await lifecycle.publish_session_activity(session_key, session)

    # The webstation broker's deferred load waits for its emulator to report
    # the game running, and holds off further until the state file is there, so
    # this push lands ahead of it even though it runs after activate.
    if resume_after_launch and resume_state is not None:
        resume_pushed = await states.push_resume_state(container, resume_state)

    await push_to_user(
        session.get("user_id"),
        "streaming:launch-ready",
        LaunchReadyPayload(
            platform=platform,
            container=session_key,
            host=container.protocol.stream_url(container.host, launch_result),
            resume=resume_pushed if resume_state is not None else None,
        ).model_dump(),
    )

    # Hydrate the container with the user's newest stored state in the
    # background, the stream should not wait on file transfers.
    background.spawn_sync_task(
        states.hydrate_states_to_broker(
            user.id, rom.id, container, resume_pushed=resume_pushed
        )
    )

    # A resumed state remembers which disc it was captured on. The launch
    # always starts on the playlist's first disc, so put the right one back.
    resume_disc_id = (
        resume_state.disc_file_id if resume_pushed and resume_state else None
    )
    if isinstance(resume_disc_id, int):
        background.spawn_sync_task(
            states.restore_session_disc(
                rom.id,
                container,
                session_key,
                file_id=resume_disc_id,
                broker_session_id=session["broker_session_id"],
            )
        )


def _failure_detail(exc: BaseException) -> str:
    """What to tell the player about a launch that never came up."""
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return "The container could not start the game"


# The player sees nothing until the stream is up, so this is the only progress
# there is.
PHASE_POLL_SECONDS = 3.0


async def _watch_launch_phase(
    container: ResolvedContainer,
    session_key: str,
    session: dict[str, Any],
    platform: str,
) -> None:
    """Push the broker's extraction phase while a launch is still running.

    Asked once here rather than per watching tab, and only changes are sent.
    """
    if not container.protocol.reports_launch_phase:
        return
    last: str | None = None
    while True:
        await asyncio.sleep(PHASE_POLL_SECONDS)
        phase = await asyncio.to_thread(webstation.launch_phase, container)
        if phase == last:
            continue
        last = phase
        await push_to_user(
            session.get("user_id"),
            "streaming:launch-phase",
            LaunchPhasePayload(
                platform=platform, container=session_key, phase=phase
            ).model_dump(),
        )
