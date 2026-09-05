"""Save-state and disc capabilities per platform and per emulator.

The broker enforces its own slot ceiling; these tables are what refuse an
out-of-range slot before the call, and they ship to the frontend via /config so
the slot selector holds no second copy.
"""

from typing import TypedDict


class _SlotCapabilities(TypedDict):
    max_slots: int  # manual save slots, selectable as 1..max_slots
    has_autosave: bool  # whether a dedicated autosave slot can be loaded
    autosave_slot: int  # that slot's index, 0 if none
    has_memory_card: bool  # whether the broker serves a whole-card /memory-card


class PlatformCapabilities(_SlotCapabilities):
    supports_disc_swap: bool  # a live swap route exists for this platform
    has_manual_disc_swap: bool  # no route, but the emulator's own UI can do it


# Keyed by platform slug (lowercase). A platform absent here gets no save-state
# UI until its broker's slot semantics are known.
_PLATFORM_CAPABILITIES: dict[str, _SlotCapabilities] = {
    # Dolphin (ngc, wii): slots 1-7 manual, slot 8 autosave. Only the
    # GameCube side has a memory card; Wii saves live in NAND and round-trip
    # through /save-file instead.
    "ngc": {
        "max_slots": 7,
        "has_autosave": True,
        "autosave_slot": 8,
        "has_memory_card": True,
    },
    "wii": {
        "max_slots": 7,
        "has_autosave": True,
        "autosave_slot": 8,
        "has_memory_card": False,
    },
    # PCSX2 (ps2): slots 1-9 manual, slot 10 autosave.
    "ps2": {
        "max_slots": 9,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": True,
    },
    # xemu (xbox) keeps the emulated HDD in raw format so its FATX partition
    # can be read directly, and a raw image cannot hold QEMU snapshots. No
    # states at all, so the launch screen reports the save instead of
    # offering slots. Saves round-trip through /save-file, not /memory-card.
    "xbox": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
    # Cemu (wiiu) has no control API and no save states at all; persistence
    # is the game's own save data under the emulated MLC, round-tripped
    # through /save-file.
    "wiiu": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
    # DuckStation (psx) has no runtime control channel. SIGTERM triggers a
    # graceful shutdown that writes one resume state, which doubles as the
    # only save the broker can produce; the slot number is carried only for
    # API symmetry, so it normalizes to the shared autosave slot like
    # RetroArch below.
    "psx": {
        "max_slots": 0,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": False,
    },
    # RPCS3 (ps3) follows DuckStation's model, not PCSX2's: the save-state
    # hotkey always terminates the process once written, and loading one
    # means booting straight into the .SAVESTAT file instead of the ROM. No
    # live slots, one resume state.
    "ps3": {
        "max_slots": 0,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": False,
    },
    # Azahar (3ds) has no control API and no save states; persistence is the
    # game's own save data under the emulated SD card and NAND.
    "3ds": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
    # shadPS4 (ps4) has no save states; persistence is the game's own save
    # data under the emulated user savedata tree.
    "ps4": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
    # Xenia (xbox360) has no save states and no external control API;
    # persistence is the game's own save data under the emulated content
    # tree, written through on every guest save.
    "xbox360": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
    # Eden (switch) has no save states and no external control API;
    # persistence is the game's own save data under the emulated NAND.
    "switch": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
}

NO_CAPABILITIES: _SlotCapabilities = {
    "max_slots": 0,
    "has_autosave": False,
    "autosave_slot": 0,
    "has_memory_card": False,
}

# Keyed by emulator, consulted when the platform itself is not listed above.
# RetroArch serves dozens of platforms from one container and the operator
# picks which in their config, so enumerating them here would be a second copy
# of the broker's core table that goes stale the moment the broker gains a
# platform.
_EMULATOR_CAPABILITIES: dict[str, _SlotCapabilities] = {
    # The webstation broker resolves every state route to a single working
    # slot, since RomM is the library of states. There is no grid to pick
    # from, just the one slot save and resume both land in.
    "retroarch": {
        "max_slots": 0,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": False,
    },
    # ScummVM saves are its states, so the broker's one working slot is both
    # what a save-state writes and what a resume loads. No memory card exists,
    # and its own slot 0 autosave rides the save archive rather than the state
    # routes.
    "scummvm": {
        "max_slots": 0,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": False,
    },
}


# Platforms whose emulator can change discs on a running game. Kept apart from
# the tables above because those are keyed by platform or by emulator and this
# is neither: RetroArch serves dozens of platforms and only these five load a
# playlist its tray commands can step through.
_DISC_SWAP_PLATFORMS = frozenset({"dc", "saturn", "segacd", "turbografx-cd", "dos"})

# Platforms with no swap route but a working manual swap inside the emulator's
# own UI. The frontend shows this as a static hint, not a control.
_MANUAL_DISC_SWAP_PLATFORMS = frozenset({"ps2"})


def slot_capabilities(platform: str, emulator: str = "") -> PlatformCapabilities:
    """Save-state and disc capabilities for a platform, or a no-slots default.

    A platform listed explicitly wins, so a platform served by more than one
    emulator keeps the semantics its own entry describes; `emulator` is the
    fallback for a container whose platform is not listed. The disc flags are
    an overlay on top of that, keyed only by platform.
    """
    platform = platform.lower()
    base = _PLATFORM_CAPABILITIES.get(platform) or _EMULATOR_CAPABILITIES.get(
        emulator.strip().lower(), NO_CAPABILITIES
    )
    return {
        "max_slots": base["max_slots"],
        "has_autosave": base["has_autosave"],
        "autosave_slot": base["autosave_slot"],
        "has_memory_card": base["has_memory_card"],
        "supports_disc_swap": platform in _DISC_SWAP_PLATFORMS,
        "has_manual_disc_swap": platform in _MANUAL_DISC_SWAP_PLATFORMS,
    }


def known_to_lack_memory_card(platform: str) -> bool:
    """True only for a platform listed above as having no memory card.

    An unlisted platform is unknown, not cardless. The operator opted in and
    their broker may well serve /memory-card, so the flag is honoured there.
    """
    capabilities = _PLATFORM_CAPABILITIES.get(platform.lower())
    return capabilities is not None and not capabilities["has_memory_card"]


# Coarse request-body bound, derived from the tables so the slot range lives in
# exactly one place. The per-platform check in the routes is the tighter,
# authoritative guard; this just rejects obviously out-of-range input up front.
MAX_SLOT = max(
    (
        max(c["max_slots"], c["autosave_slot"])
        for c in (*_PLATFORM_CAPABILITIES.values(), *_EMULATOR_CAPABILITIES.values())
    ),
    default=1,
)


class StateTransferLimits(TypedDict):
    max_bytes: int  # largest state body exchanged with the broker
    timeout: int  # seconds allowed for that body, in either direction


# urllib's timeout bounds a single socket operation, not the transfer, so the
# ceiling here is what a whole body is allowed to take.
_DEFAULT_TRANSFER_TIMEOUT = 60

DEFAULT_STATE_TRANSFER: StateTransferLimits = {
    "max_bytes": 256 * 1024 * 1024,
    "timeout": _DEFAULT_TRANSFER_TIMEOUT,
}

# Keyed by emulator name, lowercased.
_STATE_TRANSFER_LIMITS: dict[str, StateTransferLimits] = {
    # The xemu broker caps its expanded hard disk image at 2 GiB, and transfers
    # run around 18 MB/s, so a full-size archive needs minutes, not seconds.
    "xemu": {"max_bytes": 2 * 1024 * 1024 * 1024, "timeout": 240},
}


def state_transfer_limits(emulator: str) -> StateTransferLimits:
    return _STATE_TRANSFER_LIMITS.get(emulator.strip().lower(), DEFAULT_STATE_TRANSFER)
