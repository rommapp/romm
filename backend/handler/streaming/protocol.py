"""The two broker shapes: the webstation one, and the deprecated per-emulator mods.

They differ in route prefixes, timeouts, what an accepted call looks like in the
reply, and which verbs exist at all. See https://docs.romm.app/latest/using/emulator-streaming-migration/
for the config each one takes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from config import STREAMING_SAVE_TIMEOUT
from logger.logger import log

# A verb the broker only acknowledges: it answers as soon as it has accepted
# the request, not when the emulator is done.
ACK_TIMEOUT = 5


def room_url_on(host: str, room_url: str) -> str:
    """A broker's room URL resolved against the container it came from.

    The reply is the broker's own, and urljoin keeps an absolute URL (or an
    opaque `javascript:`) verbatim, so an answer that leaves the configured
    host is dropped rather than handed to a browser as an iframe source.
    """
    if not room_url:
        return host
    resolved = urljoin(host, room_url)
    base, target = urlparse(host), urlparse(resolved)
    # A container reverse proxied onto RomM's own origin is configured as a
    # bare path, and its rooms stay paths.
    on_host = (
        (target.scheme, target.netloc) == (base.scheme, base.netloc)
        if base.scheme
        else not target.scheme and not target.netloc
    )
    if not on_host:
        log.warning("broker answered with a room URL off its own host, ignoring it")
        return host
    return resolved


class BrokerProtocol:
    """Where a broker's routes live and what its answers mean."""

    name: str
    # Whether the broker has a tray route that can change discs on a running
    # game. Without it the frontend must not offer the control at all.
    supports_disc_swap: bool
    # Whether a second viewer can be given a seat on a running session.
    supports_join: bool
    # Whether the container can run a bare desktop rather than an emulator.
    supports_desktop: bool
    # Whether save-and-exit can be told not to wait for the save to land.
    supports_background_exit: bool
    # Whether the broker reports how far a long launch has got. Without it a
    # launch is opaque until it finishes.
    reports_launch_phase: bool
    # What save-state may take, and the key its reply reports success under.
    save_state_timeout: int
    _save_state_key: str

    def session_route(self, path: str) -> str:
        """A session control verb (`/launch`, `/save-state`, `/stop`, ...)."""
        raise NotImplementedError

    def transfer_route(self, path: str) -> str:
        """A state or memory card body transfer."""
        raise NotImplementedError

    def memory_card_route(self, emulator: str, platform: str) -> str:
        """Where this broker serves the whole Slot-1 card."""
        raise NotImplementedError

    def save_state_accepted(self, body: dict[str, Any] | None) -> bool:
        """Whether a /save-state reply means the save is under way."""
        return bool(body and body.get(self._save_state_key, False))

    def stream_url(self, host: str, launch_result: Any) -> str:
        """The iframe URL for a session this broker just started, carrying
        whatever credential its launch reply handed back."""
        raise NotImplementedError


class LegacyBrokerProtocol(BrokerProtocol):
    """A per-emulator broker mod, serving one emulator off the container root.

    Deprecated, kept working for one more release. Its save-state is
    asynchronous: the reply says the write started, not that it finished.
    """

    name = "legacy"
    supports_disc_swap = False
    supports_join = False
    supports_desktop = False
    supports_background_exit = True
    reports_launch_phase = False
    save_state_timeout = ACK_TIMEOUT
    _save_state_key = "status"

    def session_route(self, path: str) -> str:
        return path

    def transfer_route(self, path: str) -> str:
        return path

    def memory_card_route(self, emulator: str, platform: str) -> str:
        # It serves the one card it has, and ignores which emulator asked.
        return "/memory-card"

    def save_state_accepted(self, body: dict[str, Any] | None) -> bool:
        return bool(body and body.get("status") == "saving")

    def stream_url(self, host: str, launch_result: Any) -> str:
        # The broker mints a stream token bound to this session and returns it
        # in the launch body. Appended so the iframe URL carries it; the broker
        # swaps it for a cookie on first load. No token means the gate is not
        # deployed on that container, so the host is left untouched.
        token = (
            launch_result.get("stream_token", "")
            if isinstance(launch_result, dict)
            else ""
        )
        if not token:
            return host
        separator = "&" if "?" in host else "?"
        return f"{host}{separator}stream_token={token}"


class WebstationProtocol(BrokerProtocol):
    """The webstation broker: several emulators behind one subfolder.

    Its save-state is synchronous (it answers once the emulator acked the
    write), so it needs the same budget as an exit save.
    """

    name = "webstation"
    supports_disc_swap = True
    supports_join = True
    supports_desktop = True
    supports_background_exit = False
    reports_launch_phase = True
    save_state_timeout = STREAMING_SAVE_TIMEOUT
    _save_state_key = "saved"

    def __init__(self, subfolder: str = "/streaming") -> None:
        cleaned = subfolder.strip() or "/streaming"
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        self.subfolder = cleaned.rstrip("/")

    def session_route(self, path: str) -> str:
        return f"{self.subfolder}/api/session{path}"

    def transfer_route(self, path: str) -> str:
        return self.session_route(path)

    def memory_card_route(self, emulator: str, platform: str) -> str:
        # One container hosts several emulators and the card belongs to the
        # emulator, not the session. The platform disambiguates an emulator
        # that only has a card on some of what it serves (Dolphin: GC, not Wii).
        query = (
            f"emulator={quote(emulator, safe='')}&platform={quote(platform, safe='')}"
        )
        return self.transfer_route(f"/memory-card?{query}")

    def stream_url(self, host: str, launch_result: Any) -> str:
        # Activate answers with the room URL carrying the claiming user's
        # token, relative to the container root. An absolute path replaces
        # whatever path the configured host carries.
        room_url = (
            str(launch_result.get("url", "")) if isinstance(launch_result, dict) else ""
        )
        return room_url_on(host, room_url)


LEGACY_PROTOCOL = LegacyBrokerProtocol()


# Interned per subfolder, so two containers configured the same way share one
# protocol object and the records holding them compare equal.
@lru_cache(maxsize=None)
def _webstation_protocol(subfolder: str) -> WebstationProtocol:
    return WebstationProtocol(subfolder)


def protocol_for(protocol_name: Any, subfolder: Any) -> BrokerProtocol:
    """The protocol a raw container entry declares. Anything but an explicit
    `protocol: webstation` is the deprecated per-emulator shape."""
    if str(protocol_name or "").strip().lower() != "webstation":
        return LEGACY_PROTOCOL
    return _webstation_protocol(str(subfolder or "/streaming"))
