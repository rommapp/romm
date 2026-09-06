"""The verbs RomM sends a container: launch, stop, save, load, swap, volume.

Each one hides the two broker protocols behind a single call, so a route asks
for the effect and never for the route that produces it.
"""

import urllib.error
from typing import Any

from config import STREAMING_SAVE_TIMEOUT
from handler.streaming import broker, webstation
from handler.streaming.config import ResolvedContainer
from handler.streaming.protocol import ACK_TIMEOUT
from logger.logger import log


def launch(
    container: ResolvedContainer,
    rom_path: str,
    rom_name: str,
    load_slot: int | None = None,
) -> dict[str, Any]:
    """
    POST to the broker's /launch endpoint to tell the emulator container to
    load a ROM.

    With load_slot set the broker loads that save-state slot once the game
    is up (resume-from-state). Raises HTTPException if the broker is
    unreachable or returns an error. Returns the parsed launch response body.
    """
    url = broker.broker_url(container, "/launch")
    body: dict[str, Any] = {"rom_path": rom_path, "rom_name": rom_name}
    if load_slot is not None:
        body["load_slot"] = load_slot
    try:
        resp = broker.request(
            container, "/launch", body=body, timeout=broker.LAUNCH_TIMEOUT
        )
        log.info("broker launched ROM, %s", resp)
        return resp if isinstance(resp, dict) else {}
    except urllib.error.HTTPError as exc:
        broker.raise_http_error(exc)
    except (urllib.error.URLError, OSError) as exc:
        broker.raise_unreachable(
            exc,
            "ROM broker",
            url,
            "Check that broker.py is running inside the emulator container "
            "and that port 8000 is reachable from the RomM host.",
        )


def save_and_exit(
    container: ResolvedContainer, slot: int = 0, wait: bool = True
) -> tuple[bool, int]:
    """
    POST /save-and-exit to the broker. Best-effort, logs but never raises.
    With wait=True the call blocks until save+kill completes (use for button press).
    With wait=False the broker fires save+kill in the background (use for navigation away).
    Returns (saved, slot). Brokers resolve slot 0 to their default autosave
    slot and echo the effective slot back, which the state sync needs to pull
    the right file afterwards.
    """
    # Waiting brokers can legitimately block for a while: rpcs3 polls the
    # savestate write for up to SAVE_WAIT (30s default) and xemu's QMP
    # save + reset path can approach that too. Time out past the slowest
    # broker so a slow-but-successful save is not reported as saved=False.
    # Overridable for operators who raise SAVE_WAIT on a broker.
    if container.is_webstation:
        # No background variant on this protocol: exit always runs the save,
        # the teardown and the save dump together before it answers.
        report = webstation.exit_session(container, slot)
        saved = bool(report and report.get("state_saved", False))
        effective_slot = slot
        if report is not None and isinstance(report.get("state_slot"), int):
            effective_slot = report["state_slot"]
        log.info("broker exit, saved=%s slot=%d", saved, effective_slot)
        return saved, effective_slot

    body = broker.request_safe(
        container,
        "/save-and-exit",
        "save-and-exit",
        body={"slot": slot, "wait": wait},
        timeout=STREAMING_SAVE_TIMEOUT if wait else ACK_TIMEOUT,
    )
    saved = bool(body and body.get("saved", False))
    effective_slot = slot
    if body is not None and isinstance(body.get("slot"), int):
        effective_slot = body["slot"]
    log.info(
        "broker save-and-exit, saved=%s slot=%d wait=%s", saved, effective_slot, wait
    )
    return saved, effective_slot


def set_volume(container: ResolvedContainer, level: int) -> bool:
    """POST /volume to the broker. Best-effort, logs but never raises."""
    body = broker.request_safe(
        container,
        "/volume",
        "volume",
        body={"level": level},
        timeout=ACK_TIMEOUT,
    )
    return bool(body and body.get("status") == "ok")


def set_mute(container: ResolvedContainer, mute: bool | None) -> bool | None:
    """POST /mute to the broker. Returns confirmed mute state, or None on error."""
    body = broker.request_safe(
        container,
        "/mute",
        "mute",
        body={} if mute is None else {"mute": mute},
        timeout=ACK_TIMEOUT,
    )
    return body.get("mute") if body is not None else None


def save_state(container: ResolvedContainer, slot: int) -> bool:
    """POST /save-state to the broker. Returns True if the request was accepted.

    One protocol answers once the emulator acked the write and the other as
    soon as it has started, so both the budget and the key that reports success
    come from the protocol.
    """
    protocol = container.protocol
    body = broker.request_safe(
        container,
        protocol.session_route("/save-state"),
        "save-state",
        body={"slot": slot},
        timeout=protocol.save_state_timeout,
    )
    return protocol.save_state_accepted(body)


def load_state(container: ResolvedContainer, slot: int) -> bool:
    """POST /load-state to the broker. Returns True if broker confirmed success.

    Both protocols answer the same way here, so only the route differs. The
    timeout covers the worst case: 9 slot cycles x ~5s xdotool timeout.
    """
    body = broker.request_safe(
        container,
        container.protocol.transfer_route("/load-state"),
        "load-state",
        body={"slot": slot},
        timeout=broker.LOAD_STATE_TIMEOUT,
    )
    return bool(body and body.get("loaded", False))


def swap_disc(container: ResolvedContainer, disc_path: str) -> bool:
    """POST /swap-disc to the broker. True once the disc is mounted.

    A protocol without a tray has no route to call, so there is nothing to try.
    """
    if not container.protocol.supports_disc_swap:
        return False
    body = broker.request_safe(
        container,
        container.protocol.session_route("/swap-disc"),
        "swap-disc",
        body={"path": disc_path},
        timeout=broker.SWAP_DISC_TIMEOUT,
    )
    return bool(body and body.get("status") == "ok")


def stop(container: ResolvedContainer, save: bool = True) -> int | None:
    """Tell the broker to stop emulator. Best-effort, don't raise on failure.

    Returns the slot a state was captured in, or None when none was. With
    `save` off no state is written at all, which is what a player leaving
    without saving asked for; the game's own save data still travels either
    way, so progress made at an in-game save point survives the stop.

    `save` only reaches webstation containers. The per-emulator brokers have
    one stop and it writes no state, so they are already what `save` off asks
    for and there is nothing to pass them.
    """
    if container.is_webstation:
        report = webstation.exit_session(container, slot=0, save=save)
        if save and report and report.get("state_saved"):
            slot = report.get("state_slot")
            return slot if isinstance(slot, int) else None
        return None
    broker.request_safe(
        container, "/launch", "stop", method="DELETE", timeout=ACK_TIMEOUT
    )
    return None
