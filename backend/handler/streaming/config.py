"""Streaming containers, resolved once from config.yml into frozen records.

The raw YAML is loose: a container may serve one platform or a map of them, and
may leave its broker host to be derived. Resolution is memoized until the config
changes, so an unusable container is reported once rather than once per lookup.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

from config import LIBRARY_BASE_PATH, STREAMING_BROKER_SECRET
from config.config_manager import config_manager as cm
from handler.streaming.capabilities import (
    PlatformCapabilities,
    StateTransferLimits,
    known_to_lack_memory_card,
    slot_capabilities,
    state_transfer_limits,
)
from handler.streaming.protocol import BrokerProtocol, protocol_for
from logger.logger import log

# Keys a `platforms:` block may override for the one platform it names.
PLATFORM_OVERRIDE_KEYS = ("emulator", "label", "memory_card_sync")

# Play-button text per emulator, used when a platform block sets no `label`
# of its own. Keyed by emulator name as the broker registers it (lowercase).
_EMULATOR_DISPLAY_NAMES: dict[str, str] = {
    "azahar": "Azahar",
    "cemu": "Cemu",
    "desktop": "Desktop",
    "dolphin": "Dolphin",
    "duckstation": "DuckStation",
    "eden": "Eden",
    "flycast": "Flycast",
    "pcsx2": "PCSX2",
    "ppsspp": "PPSSPP",
    "rpcs3": "RPCS3",
    "shadps4": "shadPS4",
    "xemu": "xemu",
    "xenia": "Xenia",
}

# Display name of the libretro core the broker's RetroArch launcher picks for
# each platform (its retroarch_platforms.json). Display only: RomM never
# selects cores. A platform missing here is labelled by its slug instead.
_RETROARCH_CORE_NAMES: dict[str, str] = {
    "3do": "Opera",
    "3ds": "Azahar",
    "amiga": "PUAE",
    "arcade": "FinalBurn Neo",
    "atari-st": "Hatari",
    "atari2600": "Stella",
    "atari5200": "a5200",
    "atari7800": "ProSystem",
    "c64": "VICE",
    "colecovision": "Gearcoleco",
    "cps1": "FinalBurn Neo",
    "cps2": "FinalBurn Neo",
    "cps3": "FinalBurn Neo",
    "dc": "Flycast",
    "dos": "DOSBox Pure",
    "famicom": "Mesen",
    "fds": "Mesen",
    "gamegear": "Genesis Plus GX",
    "gb": "Gambatte",
    "gba": "mGBA",
    "gbc": "Gambatte",
    "genesis": "Genesis Plus GX",
    "intellivision": "FreeIntv",
    "jaguar": "Virtual Jaguar",
    "lynx": "Handy",
    "msx": "blueMSX",
    "msx2": "blueMSX",
    "n64": "Mupen64Plus-Next",
    "nds": "melonDS",
    "neo-geo-cd": "NeoCD",
    "neo-geo-pocket": "Beetle NGP",
    "neo-geo-pocket-color": "Beetle NGP",
    "neogeoaes": "FinalBurn Neo",
    "neogeomvs": "FinalBurn Neo",
    "nes": "Mesen",
    "ngc": "Dolphin",
    "odyssey-2": "O2EM",
    "psp": "PPSSPP",
    "psx": "SwanStation",
    "saturn": "Yaba Sanshiro",
    "sega32": "PicoDrive",
    "segacd": "Genesis Plus GX",
    "sfam": "Snes9x",
    "sg1000": "Genesis Plus GX",
    "sms": "Genesis Plus GX",
    "snes": "Snes9x",
    "supergrafx": "Beetle SuperGrafx",
    "tg16": "Beetle PCE",
    "turbografx-cd": "Beetle PCE",
    "vectrex": "vecx",
    "virtualboy": "Beetle VB",
    "wii": "Dolphin",
    "wonderswan": "Beetle WonderSwan",
    "wonderswan-color": "Beetle WonderSwan",
    "zxs": "Fuse",
}


def emulator_display_label(emulator: str, platform: str) -> str:
    """Play-button text for an emulator serving a platform, e.g. "PCSX2" or
    "RA PPSSPP". Unknown emulators fall back to their configured name."""
    key = emulator.strip().lower()
    if key == "retroarch":
        core = _RETROARCH_CORE_NAMES.get(platform.lower(), platform.upper())
        return f"RA {core}"
    return _EMULATOR_DISPLAY_NAMES.get(key, emulator.strip())


@dataclass(frozen=True)
class ResolvedContainer:
    """One (container, platform) pair, with every question already answered.

    A container serving several platforms yields one record each, all sharing a
    `key`: it is one container and can hold one session.
    """

    key: str
    """Stable identity, derived from the broker host. Empty is unclaimable."""
    host: str
    """Browser-facing stream URL, or a path when reverse proxied onto the app."""
    broker_host: str | None
    """Server-to-server API base, or None when nothing reachable was named."""
    protocol: BrokerProtocol
    platform: str
    emulator: str
    """Namespace for stored states and cards, e.g. 'pcsx2'."""
    label: str
    """What the Play button says for this platform."""
    container_label: str | None
    """The container's own label, before any per-platform override."""
    memory_card_sync: bool
    """Whole-card sync, already checked against the platform having a card."""
    broker_secret: str
    library_path: str
    """Where the container sees the ROM library, when it differs from RomM's."""
    capabilities: PlatformCapabilities
    state_transfer: StateTransferLimits

    @property
    def is_webstation(self) -> bool:
        return self.protocol.name == "webstation"

    def interchangeable_with(self, other: ResolvedContainer) -> bool:
        """Whether two containers serving a platform are a pool rather than two
        different setups. The emulator names the state and card namespace, and
        whole-card sync decides whether cards are synced at all, so a player
        landing on either has to find their saves in the same place. The
        protocol decides which controls exist at all (disc swap, joining), and
        those are advertised from the head of the pool, so a member that
        disagrees would offer a control that 502s on half the claims."""
        return (
            self.emulator == other.emulator
            and self.memory_card_sync == other.memory_card_sync
            # Protocols are interned per subfolder, so identity is equality.
            and self.protocol is other.protocol
        )

    def memory_card_route(self) -> str:
        return self.protocol.memory_card_route(self.emulator, self.platform)


def _loggable(entry: dict[str, Any]) -> dict[str, Any]:
    """A raw config entry without its shared secret, so a warning can name the
    container it means without printing the secret into the log."""
    redacted = {k: v for k, v in entry.items() if k != "broker_secret"}
    platforms = redacted.get("platforms")
    if isinstance(platforms, dict):
        redacted["platforms"] = {
            platform: _loggable(options) if isinstance(options, dict) else options
            for platform, options in platforms.items()
        }
    return redacted


def parse_host_url(host: str) -> str | None:
    """Validate a configured host/broker_host and return it stripped, or None
    when it has no scheme (urlparse yields hostname=None for a bare
    'host:port', which would produce the broken '//None:8000/...' string).
    Operators must write a scheme, matching the documented config examples."""
    host = host.strip().rstrip("/")
    if not host:
        return None
    parsed = urlparse(host)
    if not parsed.scheme or not parsed.hostname:
        return None
    return host


def parse_stream_host(host: str) -> str | None:
    """Validate a configured stream host: an absolute URL, or a path when the
    container is reverse proxied onto RomM's own origin (`/streaming`). The
    browser resolves a path against whatever origin it is already on, which is
    what makes the iframe same origin and its pointer events reachable."""
    host = host.strip()
    if host.startswith("/"):
        return host.rstrip("/") or "/"
    return parse_host_url(host)


def _derive_broker_host(entry: dict[str, Any], protocol: BrokerProtocol) -> str | None:
    """Resolve the broker API host for a raw entry.

    A webstation container serves the broker on the stream's own origin; the
    per-emulator mods serve it on port 8000. None for a container proxied onto
    a bare path, which carries no address to dial.
    """
    broker_host = parse_host_url(str(entry.get("broker_host", "")))
    if broker_host:
        return broker_host.rstrip("/")
    stream_host = parse_host_url(str(entry.get("host", "")))
    if not stream_host:
        return None
    if protocol.name == "webstation":
        return stream_host.rstrip("/")
    parsed = urlparse(stream_host)
    return urlunparse(parsed._replace(netloc=f"{parsed.hostname}:8000")).rstrip("/")


def _emulator_namespace(entry: dict[str, Any]) -> str:
    """Namespace for stored states, e.g. 'pcsx2'. Keeps streaming states apart
    from the EmulatorJS states of the same ROM."""
    value = entry.get("emulator") or entry.get("label") or entry.get("platform") or ""
    return str(value).strip().lower()


def _resolve_one(
    entry: dict[str, Any], platform: str, container_label: Any
) -> ResolvedContainer:
    """One resolved record for a (container, platform) pair.

    An unreachable container still resolves, with an empty `key`: it cannot be
    claimed, but the fleet view lists it so the misconfiguration is visible.
    """
    protocol = protocol_for(entry.get("protocol"), entry.get("subfolder"))

    broker_host: str | None = None
    if not parse_stream_host(str(entry.get("host", ""))):
        log.warning(
            "container for platform '%s' missing a scheme-bearing host or a "
            "proxied path, it cannot be claimed: %s",
            platform,
            _loggable(entry),
        )
    else:
        broker_host = _derive_broker_host(entry, protocol)
        if not broker_host:
            # A proxied host carries no address RomM can call, so the broker is
            # only reachable if the operator named it.
            log.warning(
                "container for platform '%s' has no reachable broker, set "
                "broker_host, it cannot be claimed: %s",
                platform,
                _loggable(entry),
            )

    emulator = _emulator_namespace(entry)
    card_sync = bool(entry.get("memory_card_sync", False))
    if card_sync and known_to_lack_memory_card(platform):
        # Honouring the flag here would be silent data loss: whole-card sync
        # REPLACES /save-file, so the per-file saves this platform actually
        # uses (Wii NAND, xemu HDD) would stop syncing while RomM shuttled an
        # empty card around.
        log.warning(
            "container for platform '%s' sets memory_card_sync but that "
            "platform has no memory card, ignoring the flag and syncing "
            "individual save files instead",
            platform,
        )
        card_sync = False

    capabilities = slot_capabilities(platform, emulator)
    if not protocol.supports_disc_swap:
        # Disc swap is keyed by platform, but only the webstation broker has a
        # tray route: a legacy container must not advertise a control whose
        # every use 502s.
        capabilities = {**capabilities, "supports_disc_swap": False}

    label = entry.get("label")
    return ResolvedContainer(
        key=broker_host or "",
        host=str(entry.get("host", "")),
        broker_host=broker_host,
        protocol=protocol,
        platform=platform,
        emulator=emulator,
        label=str(label) if label else emulator_display_label(emulator, platform),
        container_label=container_label if isinstance(container_label, str) else None,
        memory_card_sync=card_sync,
        broker_secret=STREAMING_BROKER_SECRET or str(entry.get("broker_secret", "")),
        library_path=str(entry.get("library_path") or LIBRARY_BASE_PATH).rstrip("/"),
        capabilities=capabilities,
        state_transfer=state_transfer_limits(emulator),
    )


def _platform_entries(entry: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    """The (raw entry, platform) pairs one config entry expands into.

    A container declaring `platforms` yields one per platform with its
    overrides folded in; a flat entry yields itself.
    """
    platforms = entry.get("platforms")
    if platforms is None:
        platform = str(entry.get("platform", "")).strip()
        if not platform:
            log.warning(
                "container missing platform/host, skipping: %s", _loggable(entry)
            )
            return []
        return [(entry, platform)]

    if not isinstance(platforms, dict):
        log.warning(
            "container `platforms` must be a map of platform to emulator, "
            "skipping: %s",
            _loggable(entry),
        )
        return []
    if entry.get("platform"):
        log.warning(
            "container declares both `platform` and `platforms`, "
            "serving `platforms` only: %s",
            _loggable(entry),
        )

    base = {k: v for k, v in entry.items() if k != "platforms"}
    rows: list[tuple[dict[str, Any], str]] = []
    for platform, options in platforms.items():
        if not isinstance(platform, str) or not platform.strip():
            log.warning("container platform key is not a name, skipping: %r", platform)
            continue
        row = _platform_overrides(base, platform.strip(), options)
        if row is not None:
            rows.append((row, platform.strip()))
    return rows


def _platform_overrides(
    base: dict[str, Any], platform: str, options: Any
) -> dict[str, Any] | None:
    """One raw row for a platform, or None when the block is unusable.

    `options` is either the emulator name or a block overriding container keys.
    """
    if isinstance(options, str):
        emulator = options.strip()
        overrides: dict[str, Any] = {}
    elif isinstance(options, dict):
        raw = options.get("emulator")
        emulator = raw.strip() if isinstance(raw, str) else ""
        overrides = {
            k: v
            for k, v in options.items()
            if k in PLATFORM_OVERRIDE_KEYS and k != "emulator"
        }
        for key in options:
            if key not in PLATFORM_OVERRIDE_KEYS:
                log.warning(
                    "container platform '%s' sets unknown option '%s', ignoring",
                    platform,
                    key,
                )
    else:
        log.warning(
            "container platform '%s' must name an emulator or set a block of "
            "options, skipping",
            platform,
        )
        return None

    if not emulator:
        # The emulator names the state and card namespace, so guessing one
        # would file this platform's saves under another container.
        log.warning("container platform '%s' has no emulator, skipping", platform)
        return None

    # A platform block's own `label` wins; otherwise the emulator names the
    # button, not the container, so "Stream on PCSX2" rather than the box.
    label = overrides.get("label") or emulator_display_label(emulator, platform)
    return {
        **base,
        **overrides,
        "platform": platform,
        "emulator": emulator,
        "label": label,
    }


def resolve_entry(entry: dict[str, Any]) -> ResolvedContainer | None:
    """Resolve one raw config entry, taking the first platform it serves.

    For callers holding a single entry rather than the whole config; the
    whole-config path below walks every platform of every entry.
    """
    rows = _platform_entries(entry)
    if not rows:
        return None
    row, platform = rows[0]
    return _resolve_one(row, platform, entry.get("label"))


_cache_fingerprint: str | None = None
_cached: tuple[ResolvedContainer, ...] = ()


def reset_cache() -> None:
    """Drop the memoized resolution, for a caller swapping the config under a
    fingerprint already resolved."""
    global _cache_fingerprint, _cached
    _cache_fingerprint = None
    _cached = ()


def _fingerprint(raw: Any) -> str:
    try:
        return json.dumps(raw, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Unserializable config: never matches, so it re-resolves every time
        # rather than serving a record built from something else. A fresh
        # random value rather than an object's repr, which CPython happily
        # repeats when the address is reused.
        return f"unserializable:{secrets.token_hex(8)}"


def resolve_containers() -> tuple[ResolvedContainer, ...]:
    """Every usable (container, platform) pair, in config order.

    Config order is deliberate: the head of the list stays warm (shader caches,
    BIOS, memory cards) instead of players spreading across cold containers.
    """
    global _cache_fingerprint, _cached

    cfg = cm.get_config()
    if not cfg.STREAMING_ENABLED:
        return ()

    raw = cfg.STREAMING_CONTAINERS or []
    fingerprint = _fingerprint(raw)
    if fingerprint == _cache_fingerprint:
        return _cached

    resolved: list[ResolvedContainer] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        for row, platform in _platform_entries(dict(entry)):
            resolved.append(_resolve_one(row, platform, entry.get("label")))

    _cache_fingerprint = fingerprint
    _cached = tuple(resolved)
    return _cached


def containers_for_platform(platform: str) -> list[ResolvedContainer]:
    """Every container serving a platform, in config order.

    More than one entry is a pool and the claim takes the first free one, so a
    container that disagrees with the head on emulator or card sync is not a
    pool member and is left out.
    """
    lower = platform.lower()
    candidates: list[ResolvedContainer] = []
    for container in resolve_containers():
        if container.platform.lower() != lower:
            continue
        if not container.key:
            # Nothing to dial, so a claim would have nowhere to go. The fleet
            # view still lists it, which is where the operator sees why.
            continue
        if candidates and not candidates[0].interchangeable_with(container):
            log.warning(
                "container for platform '%s' disagrees with the first one on "
                "emulator, memory card sync or protocol, so it is not a pool "
                "member, skipping: %s",
                platform,
                container.key,
            )
            continue
        candidates.append(container)
    return candidates


def containers_by_key() -> dict[str, list[ResolvedContainer]]:
    """Configured containers grouped by key. A container serving several
    platforms has one record per platform, all sharing one key."""
    grouped: dict[str, list[ResolvedContainer]] = {}
    for container in resolve_containers():
        grouped.setdefault(container.key, []).append(container)
    return grouped


def container_for_session(
    grouped: dict[str, list[ResolvedContainer]], container_key: str, platform: Any
) -> ResolvedContainer | None:
    """The record a session was claimed under. Records sharing a key differ in
    the platform-keyed fields (emulator, card sync), so picking an arbitrary
    one would file the session's saves under another platform."""
    entries = grouped.get(container_key)
    if not entries:
        return None
    if isinstance(platform, str):
        lower = platform.lower()
        for entry in entries:
            if entry.platform.lower() == lower:
                return entry
    return entries[0]


def configured_emulator(platform: str) -> str:
    """The emulator a configured container serves this platform with, if any."""
    lower = platform.lower()
    for container in resolve_containers():
        if container.platform.lower() == lower:
            return container.emulator
    return ""


def streaming_enabled() -> bool:
    return bool(cm.get_config().STREAMING_ENABLED)
