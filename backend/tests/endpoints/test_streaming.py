import asyncio
import io
import json
import logging
import re
import threading
import time
import zipfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import update
from tests.factories import (
    make_platform,
    make_rom,
    make_save,
    make_screenshot,
    make_state,
)
from tests.streaming_stubs import exit_pulls_spawned_inline

from config import LIBRARY_BASE_PATH, OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from endpoints import streaming
from endpoints.responses.assets import StateSchema
from endpoints.responses.streaming import ImportRefusalSchema
from endpoints.streaming import platform_capabilities
from handler import asset_store
from handler.activity_handler import activity_handler
from handler.auth.base_handler import oauth_handler
from handler.database import (
    db_container_adoption_handler,
    db_memory_card_handler,
    db_notification_handler,
    db_play_session_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache, sync_cache
from handler.streaming import (
    access,
    broker,
    commands,
    imports,
    launch,
    lifecycle,
    memory_cards,
    saves,
    session_store,
    states,
    webstation,
)
from handler.streaming.archive import read_member
from handler.streaming.capabilities import (
    DEFAULT_STATE_TRANSFER,
    NO_CAPABILITIES,
    state_transfer_limits,
)
from handler.streaming.config import (
    CONTAINER_NAME_MAX_LENGTH,
    ResolvedContainer,
    _derive_broker_host,
    configured_emulator,
    container_for_session,
    container_names,
    containers_by_key,
    containers_for_platform,
    emulator_display_label,
    key_for_name,
    pools_for_platform,
    reset_cache,
    resolve_containers,
    resolve_entry,
)
from handler.streaming.protocol import protocol_for
from handler.streaming.session_store import (
    STREAMING_SESSION_DRAIN_SECONDS,
    STREAMING_SESSION_TTL_SECONDS,
    StreamingSessionContended,
    release_own_session,
)
from handler.sync.retroarch import sync_handler as retroarch_sync
from models.assets import (
    AUTOSAVE_SLOT,
    MemoryCard,
    MemoryCardVersion,
    Save,
    Screenshot,
    State,
)
from models.notification import NotificationKind
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
    UserPermissionOverride,
)
from models.platform import Platform
from models.rom import Rom, RomFile, SaveTargetLayout
from models.user import Role, User
from utils.memory_cards import content_hash_of_bytes
from utils.zip_cache import ensure_zipfile_writable

# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


def _reads(body: bytes):
    """A `read(n)` that drains like a socket: the body once, then EOF.

    The broker readers loop until the response runs dry, so a stub answering the
    same bytes to every call would look like a body that never ends.
    """
    chunks = iter([body])

    def read(_size: int | None = None) -> bytes:
        return next(chunks, b"")

    return read


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_streaming_sessions():
    """Streaming sessions live in Redis (fakeredis under pytest), start clean."""
    asyncio.run(async_cache.flushall())
    yield


@pytest.fixture(autouse=True)
def clear_import_spec_cache():
    """The import-spec cache is process-wide, so one case's answer must not leak."""
    with patch.dict(webstation._import_spec_cache, clear=True):
        yield


@pytest.fixture(autouse=True)
def clear_cores_cache():
    """Isolate webstation's cores-route cache per test."""
    with patch.dict(webstation._cores_cache, clear=True):
        yield


@pytest.fixture(autouse=True)
def exit_pull_queue():
    with exit_pulls_spawned_inline() as queue:
        yield queue


@pytest.fixture(autouse=True)
def no_pull_backoff(monkeypatch):
    """The pull tests assert on how many attempts happen, not on the wait."""
    monkeypatch.setattr(broker, "PULL_RETRY_DELAY", 0)


def _access_token(user: User):
    return oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


@pytest.fixture
def access_token(admin_user: User):
    return _access_token(admin_user)


@pytest.fixture
def viewer_access_token(viewer_user: User):
    return _access_token(viewer_user)


@pytest.fixture
def editor_access_token(editor_user: User):
    return _access_token(editor_user)


def _mock_cm(enabled=True, containers=None):
    """Return a mock config_manager that yields the given streaming config."""
    cfg = MagicMock()
    cfg.STREAMING_ENABLED = enabled
    cfg.STREAMING_CONTAINERS = containers or []
    return cfg


@contextmanager
def _streaming(*containers, enabled=True):
    """Patch the streaming config to serve exactly the given containers.

    The resolver memoizes on the raw config, so the cache is dropped on the way
    in and out: two tests can otherwise share a fingerprint and the second
    would see the first's resolution (and none of its warnings).
    """
    reset_cache()
    with patch(
        "handler.streaming.config.cm.get_config",
        return_value=_mock_cm(enabled=enabled, containers=list(containers)),
    ):
        try:
            yield
        finally:
            reset_cache()


def _container_for(rom: Rom, broker_host="http://192.168.1.10:8000"):
    return {
        "platform": rom.platform_slug,
        "host": "http://192.168.1.10:3000",
        "broker_host": broker_host,
    }


def _resolved(entry: dict[str, Any] | ResolvedContainer) -> ResolvedContainer:
    """The record the resolver builds for one raw entry, for a unit test that
    calls an internal directly. A record passes straight through."""
    if not isinstance(entry, dict):
        return entry
    container = resolve_entry(entry)
    assert container is not None, f"unresolvable container: {entry}"
    return container


def _first_container(platform: str):
    """The container a claim for this platform would try first, or None."""
    candidates = containers_for_platform(platform)
    return candidates[0] if candidates else None


def _rom_on(slug: str) -> Rom:
    """Create a platform with the given slug and a ROM on it."""
    platform = make_platform(slug)
    return make_rom(platform, f"{slug}-rom", fs_stem=slug)


def _add_rom_file(rom: Rom, file_name: str) -> RomFile:
    """A RomFile on `rom`, the way multi_file_rom builds them."""
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=file_name,
            file_path=f"{rom.fs_path}/{rom.fs_name}",
            file_size_bytes=1,
        )
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _load_session(key: str) -> dict[str, Any]:
    """The session stored at `key`, failing the test if nothing is there."""
    raw = asyncio.run(async_cache.get(key))
    assert raw is not None, f"no session stored at {key}"
    return cast(dict[str, Any], json.loads(raw))


def _claim(client, token, rom_id, state_id=None, save_id=None):
    body = {"rom_id": rom_id}
    if state_id is not None:
        body["state_id"] = state_id
    if save_id is not None:
        body["save_id"] = save_id
    return client.post("/api/streaming/sessions", json=body, headers=_auth(token))


@contextmanager
def _pushes() -> Iterator[list[tuple[str, dict[str, Any]]]]:
    """Collect what the backend pushed to the claiming user's tabs, which is
    where a launch's own result lands now that the claim answers before it."""
    sent: list[tuple[str, dict[str, Any]]] = []

    async def _capture(user_id: Any, event: str, payload: dict[str, Any]) -> None:
        sent.append((event, payload))

    with patch("handler.streaming.launch.push_to_user", new=_capture):
        yield sent


def _launch_ready(sent: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """The `streaming:launch-ready` payload, or {} if the launch never got there."""
    return next((p for event, p in sent if event == "streaming:launch-ready"), {})


def _claim_ok(client, token, rom_id):
    """Claim with the broker launch stubbed, the common happy-path setup."""
    with patch("handler.streaming.commands.launch"):
        return _claim(client, token, rom_id)


# ── /config ───────────────────────────────────────────────────────────────────


def test_get_config_requires_auth(client):
    assert client.get("/api/streaming/config").status_code == 401


def test_get_config_warns_on_missing_platform(client, access_token, caplog):
    # The "romm" logger has propagate=False, so caplog's handler must be
    # added directly to it rather than relying on root-logger propagation.
    bad_container = {"host": "http://192.168.1.10:3000"}  # no "platform"
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(bad_container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                response = client.get(
                    "/api/streaming/config", headers=_auth(access_token)
                )
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert response.status_code == 200
    assert response.json()["containers"] == []
    assert "missing platform/host" in caplog.text


def test_a_config_warning_does_not_print_the_broker_secret(
    client, access_token, caplog
):
    """A misconfigured container is named in the log so the operator can find
    it, and the entry naming it carries the shared secret."""
    bad_container = {
        "host": "192.168.1.10:3000",  # no scheme
        "platforms": {"ps2": {"emulator": "pcsx2", "broker_secret": "nested"}},
        "broker_secret": "hunter2",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(bad_container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                client.get("/api/streaming/config", headers=_auth(access_token))
    finally:
        romm_logger.removeHandler(caplog.handler)

    assert "it cannot be claimed" in caplog.text
    assert "hunter2" not in caplog.text
    assert "nested" not in caplog.text


def test_get_config_ships_platform_capabilities(client, access_token):
    """The slot capabilities the frontend selector reads come from /config, so
    they are not a second hardcoded copy."""
    container = {"platform": "ps2", "host": "http://192.168.1.10:3000"}
    with _streaming(container):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    assert r.json()["containers"][0]["capabilities"] == {
        "max_slots": 9,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": True,
        "supports_disc_swap": False,
        "has_manual_disc_swap": True,
    }


def test_get_config_ships_the_emulator_labels(client, access_token):
    """Saves and states are tagged with the emulator that wrote them, so the
    display names ride along rather than being copied into the frontend."""
    with _streaming({"platform": "ps2", "host": "http://192.168.1.10:3000"}):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    labels = r.json()["emulator_labels"]
    assert labels["pcsx2"] == "PCSX2"
    assert labels["play"] == "Play!"
    # The id a save carries, with no platform to pick a core from.
    assert labels["retroarch"] == "RetroArch"


def test_get_config_ships_capabilities_for_a_retroarch_platform(client, access_token):
    """RetroArch serves dozens of platforms, none of them listed by name. Without
    a fallback they all reported no states and the player offered no save
    button, only save and exit."""
    container = {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {"psp": "retroarch"},
    }
    with _streaming(container):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    caps = r.json()["containers"][0]["capabilities"]
    assert caps["has_autosave"] is True
    assert caps["autosave_slot"] == 10


def test_config_ships_the_state_core_rule(client, access_token):
    with _streaming(_webstation(platforms={"snes": "retroarch:bsnes"})):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=None
            ),
            patch("handler.streaming.webstation.default_core", return_value="snes9x"),
        ):
            body = client.get(
                "/api/streaming/config", headers=_auth(access_token)
            ).json()
    (snes,) = [c for c in body["containers"] if c["platform"] == "snes"]
    assert snes["state_core"] == {
        "expected": "bsnes",
        "default_matches": False,
        "folders": ["bsnes"],
    }


def test_config_asks_a_broker_its_spec_and_core_at_once(client, access_token):
    """So an unreachable broker costs the play screen one timeout, not two."""
    both = threading.Barrier(2, timeout=5)

    def meet(*_args, value=None):
        both.wait()
        return value

    with _streaming(_webstation(platforms={"snes": "retroarch"})):
        with (
            patch("handler.streaming.webstation.require_import_spec", side_effect=meet),
            patch(
                "handler.streaming.webstation.default_core",
                side_effect=lambda c: meet(value="snes9x"),
            ),
        ):
            r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200


def test_config_asks_every_platform_at_once(client, access_token):
    """More checks than the default thread pool holds (at most 32), so a silent
    broker still costs the play screen one timeout rather than one per wave."""
    platforms = (
        "nes snes n64 gb gbc gba genesis atari2600 pokemon-mini psp psx sms "
        "gamegear tg16 ngp wonderswan lynx"
    ).split()
    everyone = threading.Barrier(2 * len(platforms), timeout=5)

    def meet(*_args, value=None):
        everyone.wait()
        return value

    with _streaming(_webstation(platforms=dict.fromkeys(platforms, "retroarch"))):
        with (
            patch("handler.streaming.webstation.require_import_spec", side_effect=meet),
            patch(
                "handler.streaming.webstation.default_core",
                side_effect=lambda c: meet(value="snes9x"),
            ),
        ):
            r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    assert len(r.json()["containers"]) == len(platforms)


def test_overlapping_configs_share_each_broker_check(client, access_token):
    """So page loads piling up on a silent broker hold no extra threads."""
    shared_check = streaming._shared_check
    both_joined = threading.Event()
    joins: list[object] = []
    asked: list[str] = []

    def join(*args):
        joins.append(args[0])
        if len(joins) == 4:
            both_joined.set()
        return shared_check(*args)

    def stall(*_args, value=None):
        asked.append(value or "spec")
        assert both_joined.wait(timeout=5)
        return value

    with _streaming(_webstation(platforms={"snes": "retroarch"})):
        with (
            patch.object(streaming, "_shared_check", side_effect=join),
            patch(
                "handler.streaming.webstation.require_import_spec", side_effect=stall
            ),
            patch(
                "handler.streaming.webstation.default_core",
                side_effect=lambda c: stall(value="snes9x"),
            ),
            ThreadPoolExecutor(2) as pages,
        ):
            loads = [
                pages.submit(
                    client.get, "/api/streaming/config", headers=_auth(access_token)
                )
                for _ in range(2)
            ]
            responses = [load.result(timeout=10) for load in loads]
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(asked) == ["snes9x", "spec"]


def test_config_has_no_state_core_outside_retroarch(client, access_token):
    with _streaming(_webstation()):
        with patch(
            "handler.streaming.webstation.require_import_spec", return_value=None
        ):
            body = client.get(
                "/api/streaming/config", headers=_auth(access_token)
            ).json()
    assert all(c["state_core"] is None for c in body["containers"])


def test_get_config_labels_each_platform_by_its_emulator(client, access_token):
    """A shared webstation container names the button after the emulator that
    serves each platform, RetroArch after its core, unless the platform block
    sets its own label."""
    container = {
        "host": "http://box:3010",
        "protocol": "webstation",
        "label": "Emulation station",
        "platforms": {
            "wii": "dolphin",
            "psp": "retroarch",
            "ps2": {"emulator": "pcsx2", "label": "My PS2"},
        },
    }
    with _streaming(container):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    by_platform = {c["platform"]: c for c in r.json()["containers"]}
    assert by_platform["wii"]["label"] == "Dolphin"
    assert by_platform["psp"]["label"] == "RA PPSSPP"
    assert by_platform["ps2"]["label"] == "My PS2"


def test_emulator_display_label_falls_back_to_the_configured_name():
    assert emulator_display_label("retroarch", "n64") == "RA Mupen64Plus-Next"
    assert emulator_display_label("retroarch", "unknown-slug") == "RA UNKNOWN-SLUG"
    assert emulator_display_label("somethingnew", "psp") == "somethingnew"


def test_a_platform_entry_wins_over_the_emulator_fallback():
    """ngc has its own slot semantics, so serving it through RetroArch must not
    quietly replace them."""
    container = {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {"ngc": "retroarch"},
    }
    with _streaming(container):
        assert streaming.platform_capabilities("ngc")["max_slots"] == 7


# ── RetroArch core override ──────────────────────────────────────────────────


def _snes(value, **container) -> ResolvedContainer:
    """The snes record of a webstation container serving snes as `value`."""
    return _resolved(_webstation(platforms={"snes": value}, **container))


def _warnings_of(caplog, build):
    """Run `build` with the romm logger captured, returning its result."""
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="romm"):
            return build()
    finally:
        romm_logger.removeHandler(caplog.handler)


def test_the_shorthand_names_the_emulator_and_the_core():
    container = _snes("retroarch:bsnes")
    assert (container.emulator, container.core) == ("retroarch", "bsnes")
    assert container.label == "RA bsnes"


def test_the_shorthand_tolerates_spaces_around_the_colon():
    assert _snes(" retroarch : bsnes ").core == "bsnes"


def test_the_block_form_names_the_core():
    container = _snes({"emulator": "retroarch", "core": "parallel_n64"})
    assert (container.emulator, container.core) == ("retroarch", "parallel_n64")


def test_a_platform_label_wins_over_the_core_label():
    assert (
        _snes({"emulator": "retroarch", "core": "bsnes", "label": "SNES"}).label
        == "SNES"
    )


def test_no_core_leaves_the_record_as_it_was():
    container = _snes("retroarch")
    assert (container.core, container.experimental_cores) == (None, False)
    assert container.label == "RA Snes9x"


def test_a_flat_entry_takes_a_core():
    entry = {
        "platform": "snes",
        "protocol": "webstation",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "emulator": "retroarch",
        "core": "bsnes",
    }
    assert _resolved(entry).core == "bsnes"


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("pcsx2:bsnes", "only retroarch takes a core"),
        ("retroarch:", "sets an empty core"),
        ("retroarch:BSNES", "must match"),
        ({"emulator": "dolphin", "core": "bsnes"}, "only retroarch takes a core"),
        ({"emulator": "retroarch", "core": ""}, "sets an empty core"),
        ({"emulator": "retroarch", "core": None}, "sets an empty core"),
        ({"emulator": "retroarch", "core": 5}, "not a name"),
        ({"emulator": "retroarch", "core": "../x"}, "must match"),
    ],
)
def test_a_bad_core_skips_the_platform_with_a_warning(caplog, value, reason):
    """Booting the default instead would hide the typo behind a working game."""
    resolved = _warnings_of(
        caplog, lambda: resolve_entry(_webstation(platforms={"snes": value}))
    )
    assert resolved is None
    assert "container platform 'snes'" in caplog.text
    assert reason in caplog.text


def test_a_bad_core_on_a_flat_entry_skips_it(caplog):
    entry = {
        "platform": "snes",
        "host": "http://192.168.1.10:3000",
        "emulator": "retroarch",
        "core": "Bad Name",
    }
    assert _warnings_of(caplog, lambda: resolve_entry(entry)) is None
    assert "must match" in caplog.text


def test_a_container_level_core_is_ignored_beside_platforms(caplog):
    """One core serves one platform, so inheriting it would
    boot every platform in the map on it."""
    container = _warnings_of(caplog, lambda: _snes("retroarch", core="bsnes"))
    assert container.core is None
    assert "`core` beside `platforms`" in caplog.text


def test_a_quoted_false_does_not_opt_in():
    """A quoted "false" is truthy to bool(), and this opt-in runs cores
    known to be broken."""
    container = _snes(
        {"emulator": "retroarch", "core": "bsnes", "experimental_cores": "false"}
    )
    assert container.experimental_cores is False


def test_a_quoted_true_warns_that_it_does_not_opt_in(caplog):
    """The broker's refusal tells the operator to set experimental_cores, which
    they believe they did, so the log has to say why it didn't count."""
    container = _warnings_of(
        caplog,
        lambda: _snes(
            {"emulator": "retroarch", "core": "bsnes", "experimental_cores": "true"}
        ),
    )
    assert container.experimental_cores is False
    assert "experimental_cores" in caplog.text


def test_a_core_on_a_legacy_container_is_dropped_with_a_warning(caplog):
    """Only the webstation broker is sent a core, so a legacy container boots
    its default whatever is configured; the label must not claim otherwise."""
    entry = {
        "platform": "snes",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "emulator": "retroarch",
        "core": "bsnes",
    }
    resolved = _warnings_of(caplog, lambda: _expand(entry))
    assert (resolved[0].core, resolved[0].label) == (None, "RA Snes9x")
    assert "core" in caplog.text


def test_a_mapped_core_on_a_legacy_container_is_not_in_its_label(caplog):
    entry = {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {"snes": "retroarch:bsnes"},
    }
    resolved = _warnings_of(caplog, lambda: _expand(entry))
    assert (resolved[0].core, resolved[0].label) == (None, "RA Snes9x")


def test_an_explicit_label_survives_a_dropped_core(caplog):
    entry = {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {
            "snes": {"emulator": "retroarch", "core": "bsnes", "label": "Mine"}
        },
    }
    resolved = _warnings_of(caplog, lambda: _expand(entry))
    assert resolved[0].label == "Mine"


def test_the_platform_opt_in_wins_over_the_container():
    inherited = _snes("retroarch:bsnes", experimental_cores=True)
    overridden = _snes(
        {"emulator": "retroarch", "core": "bsnes", "experimental_cores": False},
        experimental_cores=True,
    )
    assert inherited.experimental_cores is True
    assert overridden.experimental_cores is False


def test_containers_on_different_cores_are_not_one_pool():
    """A claim landing on either would boot a different core
    and file its states where the other never looks."""
    assert not _snes("retroarch:bsnes").interchangeable_with(_snes("retroarch"))
    assert _snes("retroarch:bsnes").interchangeable_with(_snes("retroarch:bsnes"))
    opted = _snes("retroarch:bsnes", experimental_cores=True)
    assert not opted.interchangeable_with(_snes("retroarch:bsnes"))


def test_an_opt_in_without_a_core_does_not_split_a_pool():
    """The opt-in only goes out beside a core, so without one it changes
    nothing a claim could land on."""
    opted = _snes("retroarch", experimental_cores=True)
    assert opted.interchangeable_with(_snes("retroarch"))


def test_emulator_display_label_names_a_configured_core():
    assert emulator_display_label("retroarch", "snes", "bsnes") == "RA bsnes"
    assert emulator_display_label("retroarch", "snes", None) == "RA Snes9x"


def test_an_unconfigured_platform_still_has_no_states():
    """The fallback keys off a configured container, so a platform nobody
    streams stays out of the save-state UI."""
    with _streaming():
        assert streaming.platform_capabilities("psp") == {
            **NO_CAPABILITIES,
            "supports_disc_swap": False,
            "has_manual_disc_swap": False,
        }


@pytest.mark.parametrize("platform", ["dc", "saturn", "segacd", "turbografx-cd", "dos"])
def test_the_disc_platforms_support_a_live_swap(platform):
    assert platform_capabilities(platform)["supports_disc_swap"] is True


def test_ps2_gets_a_hint_instead_of_a_swap_control():
    caps = platform_capabilities("ps2")
    assert caps["supports_disc_swap"] is False
    assert caps["has_manual_disc_swap"] is True


def test_a_platform_with_no_tray_gets_neither():
    caps = platform_capabilities("xbox")
    assert caps["supports_disc_swap"] is False
    assert caps["has_manual_disc_swap"] is False


def test_disc_swap_does_not_disturb_the_slot_capabilities():
    """The disc flags are an overlay; a platform's slot semantics are
    whatever its own table entry already said."""
    caps = platform_capabilities("ngc")
    assert caps["max_slots"] == 7
    assert caps["autosave_slot"] == 8


def test_the_retroarch_autosave_slot_passes_slot_validation():
    """The gate in front of every state route reads the same table, so a slot
    the frontend is told about has to survive it."""
    container = {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {"psp": "retroarch"},
    }
    with _streaming(container):
        streaming._assert_valid_slot("psp", 10)
        with pytest.raises(HTTPException):
            streaming._assert_valid_slot("psp", 3)


def test_get_config_reports_memory_card_support(client, access_token, rom: Rom):
    """The picker gate: only containers with memory_card_sync report support."""
    plain = _container_for(rom)
    syncing = {**_container_for(rom), "platform": "ps2", "memory_card_sync": True}
    with _streaming(plain, syncing):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    containers = response.json()["containers"]
    supported = {c["platform"]: c["supports_memory_cards"] for c in containers}
    assert supported[rom.platform_slug] is False
    assert supported["ps2"] is True


def test_get_config_reports_save_picker_support(client, access_token, rom: Rom):
    """The picker gate: a pick other than the newest only lands where the
    broker clears the save tree first, which is a webstation emulator."""
    clearing = {
        **_container_for(rom),
        "protocol": "webstation",
        "emulator": "retroarch",
    }
    keeping = {
        **_container_for(rom),
        "platform": "ps2",
        "protocol": "webstation",
        "emulator": "pcsx2",
    }
    legacy = {**_container_for(rom), "platform": "gba", "emulator": "retroarch"}
    with _streaming(clearing, keeping, legacy):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    supported = {
        c["platform"]: c["supports_save_picker"] for c in response.json()["containers"]
    }
    assert supported[rom.platform_slug] is True
    assert supported["ps2"] is False
    # Restoring is the legacy broker's own business, so RomM cannot promise a
    # pick survives it.
    assert supported["gba"] is False


def test_get_config_reports_the_foreign_picks_each_broker_imports(
    client, access_token, rom: Rom
):
    """The picker only offers a foreign pick the claim would take, so a broker
    that declares no imports, or cannot be asked, reports none."""
    importing = {**_webstation_for(rom), "emulator": "duckstation"}
    silent = {**_webstation_for(rom), "platform": "ps2", "emulator": "pcsx2"}
    spec = webstation.ImportSpec(
        kinds=frozenset({"save", "state"}), state_channel="archive", state_slot=0
    )

    def answer(container, _emulator, _platform):
        return spec if container.platform == rom.platform_slug else None

    with _streaming(importing, silent):
        with patch(
            "handler.streaming.webstation.require_import_spec", side_effect=answer
        ):
            response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    kinds = {c["platform"]: c["import_kinds"] for c in response.json()["containers"]}
    assert kinds[rom.platform_slug] == ["save", "state"]
    assert kinds["ps2"] == []


@pytest.mark.parametrize(
    ("kinds", "channel", "slot", "expected"),
    [
        ({"save", "state"}, "archive", 0, ["save", "state"]),
        ({"state"}, "none", 0, []),
        ({"state"}, "push", None, []),
        ({"save", "memcard"}, "none", None, ["save"]),
    ],
)
def test_import_spec_pickable_kinds_match_what_the_claim_accepts(
    kinds, channel, slot, expected
):
    spec = webstation.ImportSpec(
        kinds=frozenset(kinds), state_channel=channel, state_slot=slot
    )
    assert spec.pickable_kinds() == expected


def test_clears_stale_saves_overrides_the_emulator_default(client, access_token, rom):
    """The default mirrors a flag that lives in the broker's repo, so an
    operator on a fork or a newer broker can say what theirs actually does."""
    turned_on = {
        **_container_for(rom),
        "platform": "ps2",
        "protocol": "webstation",
        "emulator": "pcsx2",
        "clears_stale_saves": True,
    }
    turned_off = {
        **_container_for(rom),
        "platform": "gba",
        "protocol": "webstation",
        "emulator": "retroarch",
        "clears_stale_saves": False,
    }
    with _streaming(turned_on, turned_off):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    supported = {
        c["platform"]: c["supports_save_picker"] for c in response.json()["containers"]
    }
    assert supported["ps2"] is True
    assert supported["gba"] is False


def test_clears_stale_saves_is_a_platform_block_override():
    """It sits alongside memory_card_sync, so one webstation can answer for
    each emulator it serves rather than for all of them at once."""
    expanded = _expand(
        {
            "host": "http://box:3010",
            "protocol": "webstation",
            "clears_stale_saves": True,
            "platforms": {
                "ps2": {"emulator": "pcsx2", "clears_stale_saves": False},
                "snes": "retroarch",
            },
        }
    )

    by_platform = {row.platform: row for row in expanded}
    assert by_platform["ps2"].clears_stale_saves is False
    # A block that omits the key falls through to the container.
    assert by_platform["snes"].clears_stale_saves is True


def test_clears_stale_saves_has_no_picker_to_gate_on_a_legacy_container(caplog):
    """Only the webstation broker takes an archive to restore, so the flag
    would promise a picker that has no route behind it."""
    entry = {
        "platform": "gba",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "emulator": "retroarch",
        "clears_stale_saves": True,
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="romm"):
            resolved = _expand(entry)
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert resolved[0].supports_save_picker is False
    assert "clears_stale_saves" in caplog.text


def test_only_a_webstation_exit_state_emulator_resumes_from_its_archive():
    """Only the webstation broker takes an archive to restore, so on any other
    protocol the resume state still has to be pushed as a file."""
    base = {
        "platform": "psx",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
    }
    webstation = {**base, "protocol": "webstation"}
    assert _resolved({**webstation, "emulator": "duckstation"}).resumes_from_archive
    assert _resolved({**webstation, "emulator": "rpcs3"}).resumes_from_archive
    assert not _resolved({**webstation, "emulator": "pcsx2"}).resumes_from_archive
    assert not _resolved({**base, "emulator": "duckstation"}).resumes_from_archive


def test_an_exit_state_emulator_offers_no_live_states():
    """DuckStation and RPCS3 brokers answer a mid-session save or load with a
    400, so the player must not offer one. psx is one platform entry whichever
    emulator serves it, so RetroArch on psx keeps its controls."""
    webstation = {
        "platform": "psx",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "protocol": "webstation",
    }
    assert not _resolved({**webstation, "emulator": "duckstation"}).supports_live_states
    assert not _resolved(
        {**webstation, "platform": "ps3", "emulator": "rpcs3"}
    ).supports_live_states
    assert _resolved({**webstation, "emulator": "retroarch"}).supports_live_states
    # No states at all is no live states either.
    assert not _resolved(
        {**webstation, "platform": "xbox", "emulator": "xemu"}
    ).supports_live_states


def test_get_config_ships_whether_a_container_takes_live_states(client, access_token):
    """The exit-state library still needs has_autosave, so the Save and Load
    buttons read their own flag rather than switching the slot off."""
    container = {
        "host": "http://box:3010",
        "protocol": "webstation",
        "platforms": {"psx": "duckstation", "gba": "retroarch"},
    }
    with _streaming(container):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    by_platform = {c["platform"]: c for c in r.json()["containers"]}
    assert by_platform["psx"]["supports_live_states"] is False
    assert by_platform["psx"]["capabilities"]["has_autosave"] is True
    assert by_platform["gba"]["supports_live_states"] is True


def test_a_container_that_disagrees_on_clearing_saves_is_a_pool_of_its_own(caplog):
    """The picker is advertised from the head of the pool, so a member that
    keeps its own newer files would take the pick and silently discard it."""
    first = {
        "platform": "ps2",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "protocol": "webstation",
        "emulator": "pcsx2",
        "clears_stale_saves": True,
    }
    second = {
        **first,
        "host": "http://192.168.1.11:3000",
        "broker_host": "http://192.168.1.11:8000",
        "clears_stale_saves": False,
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(first, second):
            with caplog.at_level(logging.WARNING, logger="romm"):
                candidates = containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert [c.clears_stale_saves for c in candidates] == [True]
    assert "never claimed for a game" in caplog.text


def test_legacy_containers_still_pool_under_an_inert_clearing_flag():
    """The flag is logged as having no effect without a webstation broker, so
    it must not quietly split a pool that would otherwise be one."""
    first = {
        "platform": "ps2",
        "host": "http://192.168.1.10:3000",
        "emulator": "pcsx2",
        "clears_stale_saves": True,
    }
    second = {
        **first,
        "host": "http://192.168.1.11:3000",
        "clears_stale_saves": False,
    }
    with _streaming(first, second):
        candidates = containers_for_platform("ps2")
    assert len(candidates) == 2


def test_memory_card_sync_ignored_on_a_platform_without_a_card(client, access_token):
    """Wii saves live in NAND and sync per file. Honouring memory_card_sync
    there would disable /save-file and silently strand every NAND save."""
    container = {
        "platform": "wii",
        "host": "http://192.168.1.10:3000",
        "memory_card_sync": True,
    }
    with _streaming(container):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    assert response.json()["containers"][0]["supports_memory_cards"] is False


def test_memory_card_sync_on_a_cardless_platform_warns_the_operator(caplog):
    """The misconfiguration is silent otherwise, so the claim path logs it.
    /config is polled continuously and deliberately stays quiet."""
    container = {
        "platform": "wii",
        "host": "http://192.168.1.10:3000",
        "memory_card_sync": True,
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                found = _first_container("wii")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert found is not None and found.platform == "wii"
    # The flag is dropped rather than honoured on a platform with no card.
    assert found.memory_card_sync is False
    assert "has no memory card" in caplog.text


def test_memory_card_sync_honoured_on_a_platform_with_a_card(client, access_token):
    """The guard rejects only the unsupported platforms, ngc keeps whole-card
    sync because Dolphin serves a Slot-A card."""
    container = {
        "platform": "ngc",
        "host": "http://192.168.1.10:3000",
        "memory_card_sync": True,
    }
    with _streaming(container):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    assert response.json()["containers"][0]["supports_memory_cards"] is True


def test_get_config_hides_a_hidden_platform(
    client, viewer_access_token, viewer_user: User, rom: Rom, platform
):
    """The entry carries the platform's label and capabilities, so a platform
    an admin hid from this user must not be listed."""
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    with _streaming(_container_for(rom)):
        response = client.get(
            "/api/streaming/config", headers=_auth(viewer_access_token)
        )
    assert response.status_code == 200
    assert response.json()["containers"] == []


def test_get_config_keeps_a_platform_the_caller_can_see(
    client, viewer_access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        response = client.get(
            "/api/streaming/config", headers=_auth(viewer_access_token)
        )
    assert response.status_code == 200
    listed = [c["platform"] for c in response.json()["containers"]]
    assert listed == [rom.platform_slug]


def test_get_config_offers_disc_swap_only_on_a_webstation_container(
    client, access_token
):
    """Only the webstation broker has a tray route. A legacy container serving
    a multi-disc platform would 502 on every swap it advertised."""
    legacy = {"platform": "dc", "host": "http://192.168.1.10:3000"}
    with _streaming(legacy):
        legacy_caps = client.get(
            "/api/streaming/config", headers=_auth(access_token)
        ).json()["containers"][0]["capabilities"]

    tray = {**legacy, "protocol": "webstation"}
    with _streaming(tray):
        ws_caps = client.get(
            "/api/streaming/config", headers=_auth(access_token)
        ).json()["containers"][0]["capabilities"]

    assert legacy_caps["supports_disc_swap"] is False
    assert ws_caps["supports_disc_swap"] is True


def test_get_config_leaves_out_a_container_no_claim_can_reach(client, access_token):
    """A host with no scheme resolves to no key, so every claim on it fails and
    listing it would put a Play button on a platform that can never stream."""
    with _streaming({"platform": "ps2", "host": "192.168.1.10:3000"}):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    assert response.json()["containers"] == []


def test_get_config_lists_a_platform_once_whatever_the_case(client, access_token):
    """Platforms are matched case-insensitively everywhere else, so two records
    naming one platform in different case are one platform to every claim."""
    with _streaming(
        {"platform": "PS2", "host": "http://box-a:3000"},
        {"platform": "ps2", "host": "http://box-b:3000"},
    ):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    assert len(response.json()["containers"]) == 1


def test_configured_emulator_names_the_container_a_claim_wins(client):
    """Slot ceilings are read off this emulator, so it has to be the one on the
    container a claim lands on, not the first record in the file."""
    with _streaming(
        {"platform": "ps2", "host": "192.168.1.10:3000", "emulator": "retroarch"},
        {
            "platform": "ps2",
            "host": "http://box:3000",
            "broker_host": "http://box:8000",
            "emulator": "pcsx2",
        },
    ):
        assert configured_emulator("ps2") == "pcsx2"


def test_configured_emulator_is_empty_without_a_claimable_container(client):
    with _streaming({"platform": "ps2", "host": "192.168.1.10:3000"}):
        assert configured_emulator("ps2") == ""


# ── Nested platform config ────────────────────────────────────────────────────


def _nested(**overrides):
    """A webstation container serving several platforms from one host."""
    return {
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "platforms": {"ps2": "pcsx2", "ngc": "dolphin"},
        **overrides,
    }


def test_nested_platforms_resolve_to_the_same_container():
    """One entry serves every platform in its map, each with its own emulator."""
    with _streaming(_nested()):
        ps2 = _first_container("ps2")
        ngc = _first_container("ngc")
    assert ps2 is not None and ngc is not None
    assert ps2.platform == "ps2"
    assert ps2.emulator == "pcsx2"
    assert ngc.emulator == "dolphin"


def test_nested_platforms_share_one_session_key():
    """Sessions key on the broker host, so the expanded copies collapse back
    to the single session the container can actually serve."""
    with _streaming(_nested()):
        ps2 = _first_container("ps2")
        ngc = _first_container("ngc")
    assert ps2 is not None and ngc is not None
    assert _key_of(ps2) == _key_of(ngc)


def test_nested_platforms_reject_a_second_claim_across_platforms(
    client, access_token, rom: Rom
):
    """The end-to-end consequence: claiming ps2 blocks ngc on the same box."""
    ngc_rom = _rom_on("ngc")
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        first = _claim_ok(client, access_token, ps2_rom.id)
        second = _claim_ok(client, access_token, ngc_rom.id)
    assert first.status_code == 202
    assert second.status_code == 409


def _webstation_nested():
    """A webstation container serving several platforms with a bare stream
    host and no explicit broker_host, the shape the example config
    documents as the headline case."""
    return {
        "host": "http://box:3010",
        "protocol": "webstation",
        "platforms": {
            "wii": "dolphin",
            "ps2": {"emulator": "pcsx2", "label": "PCSX2"},
        },
    }


def test_webstation_nested_platforms_share_one_session_key():
    """Tasks 6 and 7 each have their own tests; this pins the combination
    the example config documents: no explicit broker_host still derives one
    shared key across the container's expanded platform rows."""
    with _streaming(_webstation_nested()):
        wii = _first_container("wii")
        ps2 = _first_container("ps2")
    assert wii is not None and ps2 is not None
    assert _key_of(wii) == _key_of(ps2)
    assert _key_of(wii) == "http://box:3010"


def test_nested_platforms_ship_one_config_row_each(client, access_token):
    """The frontend reads capabilities per platform, so expansion must reach
    /config rather than stopping at the claim path."""
    with _streaming(_nested()):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    rows = {c["platform"]: c for c in r.json()["containers"]}
    assert set(rows) == {"ps2", "ngc"}
    assert rows["ngc"]["emulator"] == "dolphin"
    assert rows["ps2"]["capabilities"]["max_slots"] == 9


def test_config_keeps_one_row_per_platform(client, access_token):
    """Two containers serving the same platform are a pool, not two choices.
    The claim picks which one serves, so /config must not offer both."""
    with _streaming(_nested(), _nested(host="http://192.168.1.11:3000")):
        r = client.get("/api/streaming/config", headers=_auth(access_token))
    assert r.status_code == 200
    platforms = [c["platform"] for c in r.json()["containers"]]
    assert sorted(platforms) == ["ngc", "ps2"]


def test_flat_container_config_still_works(rom: Rom):
    """The per-emulator mods are still deployed on the flat shape."""
    with _streaming(_container_for(rom)):
        found = _first_container(rom.platform_slug)
    assert found is not None
    assert found.platform == rom.platform_slug


def test_nested_platforms_wins_over_a_flat_platform(caplog):
    """Declaring both is a half-finished migration, so say so rather than
    silently serving one platform out of the map."""
    container = _nested(platform="xbox")
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                xbox = _first_container("xbox")
                ps2 = _first_container("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert xbox is None
    assert ps2 is not None
    assert "both `platform` and `platforms`" in caplog.text


def test_nested_platform_without_an_emulator_is_skipped(caplog):
    """The emulator names the state namespace, so an entry missing one would
    silently file saves under the wrong container."""
    container = _nested(platforms={"ps2": "pcsx2", "ngc": ""})
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                assert _first_container("ngc") is None
                assert _first_container("ps2") is not None
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert "no emulator" in caplog.text


def test_platforms_that_is_not_a_map_skips_the_container(caplog):
    container = _nested(platforms=["ps2", "ngc"])
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(container):
            with caplog.at_level(logging.WARNING, logger="romm"):
                assert _first_container("ps2") is None
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert "must be a map" in caplog.text


# ── Claiming ──────────────────────────────────────────────────────────────────


def test_claim_derives_rom_path_server_side(client, access_token, rom: Rom):
    """The broker must receive a path built from the DB row, not client input."""
    with _streaming(_container_for(rom)):
        with patch("handler.streaming.commands.launch") as call_broker:
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert r.json()["rom_name"] == rom.name
    _, rom_path, _, _ = call_broker.call_args[0]
    assert rom_path == f"{LIBRARY_BASE_PATH}/{rom.full_path}"


def test_a_slow_claim_setup_keeps_its_claim_fresh(client, access_token, rom: Rom):
    """Nothing beats for the player until the stream is up, so a setup step
    outlasting the stale window would hand the container to the reaper."""

    async def slow_save_pull(*args: Any, **kwargs: Any) -> bool:
        await asyncio.sleep(0.05)
        return True

    with (
        _streaming(_container_for(rom)),
        patch.object(session_store, "_CLAIM_REFRESH_SECONDS", 0),
        patch("handler.streaming.saves.wait_for_save_pull", new=slow_save_pull),
        patch("handler.streaming.launch.run_launch", new=AsyncMock()),
    ):
        r = _claim(client, access_token, rom.id)

    assert r.status_code == 202
    stored = _load_session(session_store.session_redis_key(r.json()["container"]))
    assert stored["last_seen"] != r.json()["claimed_at"]


def test_claim_honors_container_library_path(client, access_token, rom: Rom):
    """`library_path` on the container entry replaces LIBRARY_BASE_PATH so the
    broker gets a path valid inside a container with a different mount."""
    container = {**_container_for(rom), "library_path": "/mnt/games/"}
    with _streaming(container):
        with patch("handler.streaming.commands.launch") as call_broker:
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    _, rom_path, _, _ = call_broker.call_args[0]
    assert rom_path == f"/mnt/games/{rom.full_path}"


def test_claim_appends_stream_token_to_host(client, access_token, rom: Rom):
    """The broker's stream token comes back in the launch body and rides the
    host URL to the iframe, it does not get discarded with the rest of the
    launch response."""
    container = {**_container_for(rom), "host": "https://stream.example:3001"}
    with _streaming(container):
        with patch("handler.streaming.commands.launch") as call_broker:
            call_broker.return_value = {
                "status": "launching",
                "stream_token": "tok-abc",
            }
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert (
        _launch_ready(sent)["host"]
        == "https://stream.example:3001?stream_token=tok-abc"
    )


def test_claim_appends_stream_token_with_ampersand_when_host_has_query(
    client, access_token, rom: Rom
):
    container = {
        **_container_for(rom),
        "host": "https://stream.example:3001/?path=abc",
    }
    with _streaming(container):
        with patch("handler.streaming.commands.launch") as call_broker:
            call_broker.return_value = {
                "status": "launching",
                "stream_token": "tok-abc",
            }
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert (
        _launch_ready(sent)["host"]
        == "https://stream.example:3001/?path=abc&stream_token=tok-abc"
    )


def test_claim_leaves_host_unchanged_when_broker_returns_no_token(
    client, access_token, rom: Rom
):
    """A bare MagicMock (the common stub in _claim_ok and older tests) must
    not inject a token, its .get(...) is truthy but is not a real dict."""
    container = {**_container_for(rom), "host": "https://stream.example:3001"}
    with _streaming(container):
        with patch("handler.streaming.commands.launch") as call_broker:
            call_broker.return_value = {"status": "launching"}
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert _launch_ready(sent)["host"] == "https://stream.example:3001"


def test_claim_answers_before_the_launch_and_pushes_the_room_url(
    client, access_token, rom: Rom
):
    """The claim reserves the container and returns; the URL follows.

    A launch blocks through pkg and archive extraction, so a request held open
    for it could not be cancelled by a player who changed their mind.
    """
    with _streaming(_container_for(rom)):
        with _pushes() as sent:
            r = _claim_ok(client, access_token, rom.id)

    assert r.status_code == 202
    body = r.json()
    assert body["container"] == _key_of(_container_for(rom))
    assert body["platform"] == rom.platform_slug
    # The room URL is the launch's answer, so it is not in the claim's.
    assert "host" not in body
    assert [event for event, _ in sent] == ["streaming:launch-ready"]
    assert _launch_ready(sent)["host"] == "http://192.168.1.10:3000"
    # A re-claim of the same container is only told apart by its stamp.
    assert _launch_ready(sent)["claimed_at"] == body["claimed_at"]


def test_a_failed_launch_pushes_the_reason_and_frees_the_container(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        with patch(
            "handler.streaming.commands.launch",
            side_effect=HTTPException(status_code=502, detail="broker said no"),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)

    assert r.status_code == 202
    event, payload = sent[0]
    assert event == "streaming:launch-failed"
    assert payload["detail"] == "broker said no"
    assert payload["container"] == _key_of(_container_for(rom))
    assert payload["claimed_at"] == r.json()["claimed_at"]
    assert _session_raw(_container_for(rom)) is None


def test_launch_phase_is_pushed_while_a_webstation_unpacks(
    client, access_token, rom: Rom
):
    """The client used to poll a route that had to reach the broker to answer.
    Asking once here costs one round trip however many tabs are watching."""
    phases = ["unpacking", "unpacking", "installing"]

    def _activate(*args, **kwargs):
        # Long enough for the phase watcher to tick twice.
        time.sleep(0.25)
        return {"url": "/room/x"}

    with _streaming(_webstation_for(rom)):
        with (
            patch("handler.streaming.launch.PHASE_POLL_SECONDS", 0.05),
            patch(
                "handler.streaming.webstation.launch_phase",
                side_effect=phases + ["installing"] * 20,
            ),
            patch("handler.streaming.webstation.activate", _activate),
            _spawns_nothing(),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", new=AsyncMock()
            ),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)

    assert r.status_code == 202
    phases_sent = [p for event, p in sent if event == "streaming:launch-phase"]
    # Only changes are pushed, so a repeated phase is not re-sent.
    assert [p["phase"] for p in phases_sent] == ["unpacking", "installing"]
    assert {p["claimed_at"] for p in phases_sent} == {r.json()["claimed_at"]}
    assert sent[-1][0] == "streaming:launch-ready"


def test_claim_unknown_rom_returns_404(client, access_token):
    with _streaming():
        r = _claim(client, access_token, 999999)
    assert r.status_code == 404


def test_claim_hidden_rom_is_404_masked(
    client, viewer_access_token, viewer_user: User, rom: Rom
):
    """A user with roms.read cannot claim a session for a ROM hidden from them;
    the launch must be 404-masked before any broker call."""
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    with _streaming(_container_for(rom)):
        # If the visibility check were missing this would 200 and launch.
        with patch("handler.streaming.commands.launch") as call_broker:
            r = _claim(client, viewer_access_token, rom.id)
    assert r.status_code == 404
    call_broker.assert_not_called()


def test_claim_rom_on_hidden_platform_is_404_masked(
    client, viewer_access_token, viewer_user: User, rom: Rom, platform: Platform
):
    """Hiding the parent platform cascades: its ROMs cannot be streamed either."""
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    with _streaming(_container_for(rom)):
        with patch("handler.streaming.commands.launch") as call_broker:
            r = _claim(client, viewer_access_token, rom.id)
    assert r.status_code == 404
    call_broker.assert_not_called()


def test_claim_skips_container_with_schemeless_host(client, access_token, rom: Rom):
    """A container whose host has no scheme would produce a broken broker URL
    and a colliding session key; it must be skipped (404), not a 500 KeyError."""
    bad = {"platform": rom.platform_slug, "host": "192.168.1.10:3000"}
    with _streaming(bad):
        r = _claim(client, access_token, rom.id)
    assert r.status_code == 404


def test_claim_skips_container_missing_host(client, access_token, rom: Rom):
    """An entry with platform set but host missing must not KeyError into a 500."""
    bad = {"platform": rom.platform_slug, "broker_host": "http://192.168.1.10:8000"}
    with _streaming(bad):
        r = _claim(client, access_token, rom.id)
    assert r.status_code == 404


def test_proxied_host_is_usable(rom: Rom):
    """A host that is a path names a container reverse proxied onto RomM's own
    origin, which is how the iframe ends up same origin as the player."""
    proxied = {
        "platform": rom.platform_slug,
        "host": "/streaming",
        "broker_host": "http://192.168.1.10:8000",
    }
    with _streaming(proxied):
        container = _first_container(rom.platform_slug)
    assert container is not None
    assert container.host == "/streaming"
    # The key still comes from the broker address, so proxying a container does
    # not move the session it already holds.
    assert _key_of(container) == "http://192.168.1.10:8000"


def test_claim_skips_proxied_host_without_broker_host(client, access_token, rom: Rom):
    """A proxied host carries no address RomM can call, so without broker_host
    the broker is unreachable and the entry must be skipped, not 500."""
    bad = {"platform": rom.platform_slug, "host": "/streaming"}
    with _streaming(bad):
        r = _claim(client, access_token, rom.id)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_claim_sets_session_ttl(access_token, rom: Rom):
    """A claimed session must carry a TTL so an abandoned one eventually frees
    the container instead of wedging it forever."""
    with _streaming(_container_for(rom)):
        with patch("handler.streaming.commands.launch"):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r = await ac.post(
                    "/api/streaming/sessions",
                    json={"rom_id": rom.id},
                    headers=_auth(access_token),
                )
    assert r.status_code == 202
    key = session_store.session_redis_key(_key_of(_container_for(rom)))
    ttl = await async_cache.ttl(key)
    assert ttl > 0
    assert ttl <= STREAMING_SESSION_TTL_SECONDS


def test_second_claim_on_same_container_rejected(client, access_token, rom: Rom):
    """The container is single-tenant: a second claim must 409 with the holder."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom.id)
    assert r1.status_code == 202
    assert r2.status_code == 409
    assert r2.json()["detail"]["rom_name"] == rom.name


def test_claim_session_same_container_two_platforms_rejected(
    client, access_token, admin_user: User, rom: Rom
):
    """Dolphin serves ngc and wii from one broker - second claim must be 409."""
    platform2 = make_platform("p2_slug", name="p2")
    rom2 = make_rom(platform2, "rom2")
    shared_broker = "http://192.168.1.10:8000"
    with _streaming(
        _container_for(rom, broker_host=shared_broker),
        _container_for(rom2, broker_host=shared_broker),
    ):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom2.id)
    assert r1.status_code == 202
    assert r2.status_code == 409


def test_failed_broker_launch_frees_the_claim(client, access_token, rom: Rom):
    """If the broker rejects the launch, the container must not stay claimed.

    The claim itself is already answered by then, so the failure reaches the
    player as a push rather than as the claim's own status."""
    with _streaming(_container_for(rom)):
        with patch(
            "handler.streaming.commands.launch",
            side_effect=HTTPException(status_code=503, detail="unreachable"),
        ):
            with _pushes() as sent:
                r1 = _claim(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom.id)
    assert r1.status_code == 202
    assert [event for event, _ in sent] == ["streaming:launch-failed"]
    assert sent[0][1]["detail"] == "unreachable"
    assert r2.status_code == 202


@pytest.mark.asyncio
async def test_concurrent_claim_only_one_succeeds(access_token, rom: Rom):
    """Two concurrent claims on one container: exactly one 200 and one 409."""
    with _streaming(_container_for(rom)):
        with patch("handler.streaming.commands.launch"):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://test"
            ) as ac:
                headers = _auth(access_token)
                r1, r2 = await asyncio.gather(
                    ac.post(
                        "/api/streaming/sessions",
                        json={"rom_id": rom.id},
                        headers=headers,
                    ),
                    ac.post(
                        "/api/streaming/sessions",
                        json={"rom_id": rom.id},
                        headers=headers,
                    ),
                )
    assert sorted([r1.status_code, r2.status_code]) == [202, 409]


# ── Container pool ────────────────────────────────────────────────────────────


def _pool_member(rom: Rom, index: int) -> dict[str, Any]:
    """One member of a pool serving the ROM's platform. Distinct hosts, so both
    the session key and the claim response say which member served. No label,
    since the emulator falls back to it and pool members must agree on that."""
    return {
        "platform": rom.platform_slug,
        "host": f"http://192.168.1.1{index}:3000",
        "broker_host": f"http://192.168.1.1{index}:8000",
    }


def _volume(client, token, platform: str, level: int = 42, params=None):
    return client.post(
        f"/api/streaming/sessions/{platform}/volume",
        json={"level": level},
        params=params,
        headers=_auth(token),
    )


def _session_raw(container: dict[str, Any]):
    key = session_store.session_redis_key(_key_of(container))
    return asyncio.run(async_cache.get(key))


def _drain(container: dict[str, Any]) -> None:
    session = _load_session(session_store.session_redis_key(_key_of(container)))
    token = asyncio.run(session_store.claim_drain_marker(_key_of(container), session))
    assert token is not None


def _stub_stop():
    return patch("handler.streaming.commands.stop", return_value=commands.StopOutcome())


def test_pool_claim_falls_through_to_a_free_container(
    client, access_token, viewer_access_token, rom: Rom
):
    """Another player's claim is not a 409 when a second container serves the
    platform. Rollover is for whoever has no container, not for the holder."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert [r1.status_code, r2.status_code] == [202, 202]
    # Config order, so the head of the pool stays warm.
    assert r1.json()["container"] == _key_of(_pool_member(rom, 0))
    assert r2.json()["container"] == _key_of(_pool_member(rom, 1))


def test_pool_409s_only_once_every_container_is_held(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    """One player per container, so filling a pool of two takes two of them and
    the third is the one told the platform is busy."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        r3 = _claim_ok(client, editor_access_token, rom.id)
    assert r3.status_code == 409
    assert "2 containers" in r3.json()["detail"]["message"]


def test_a_busy_pool_names_the_holder_while_a_member_drains(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    """A drain marker names nobody, so reading only the head of the pool told
    the waiting player the platform was saving while another member played on."""
    head, tail = _pool_member(rom, 0), _pool_member(rom, 1)
    with _streaming(head, tail):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        holder = json.loads(_session_raw(tail))
        _drain(head)
        r = _claim_ok(client, editor_access_token, rom.id)

    assert r.status_code == 409
    detail = r.json()["detail"]
    # One member is about to come free, which is what "try again shortly" says.
    assert detail["draining"] is True
    assert detail["rom_name"] == rom.name
    assert detail["claimed_at"] == holder["claimed_at"]


def test_a_busy_pool_reports_a_drain_on_any_member(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    """The container about to come free is the one the waiting player is told to
    wait for, wherever in the pool it sits."""
    head, tail = _pool_member(rom, 0), _pool_member(rom, 1)
    with _streaming(head, tail):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        holder = json.loads(_session_raw(head))
        _drain(tail)
        r = _claim_ok(client, editor_access_token, rom.id)

    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["draining"] is True
    assert "shutting down" in detail["message"]
    assert detail["rom_name"] == rom.name
    assert detail["claimed_at"] == holder["claimed_at"]


def test_a_claim_never_lands_in_a_later_pool(
    client, access_token, viewer_access_token, rom: Rom
):
    """Only the first pool matches the settings a claim is validated against,
    so a later pool stays out of reach even when it is the only one free."""
    later = {**_pool_member(rom, 1), "emulator": "other"}
    with _streaming(_pool_member(rom, 0), later):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, viewer_access_token, rom.id)
        assert _session_raw(later) is None
        assert len(pools_for_platform(rom.platform_slug)) == 2
    assert r1.status_code == 202
    assert r1.json()["container"] == _key_of(_pool_member(rom, 0))
    assert r2.status_code == 409


def test_a_pool_does_not_roll_its_own_holder_onto_a_second_container(
    client, access_token, rom: Rom
):
    """The holder claiming again is a 409, not a second container: status,
    heartbeat and release resolve by platform and would never reach a second."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom.id)
        free = asyncio.run(session_store.get_session(_key_of(_pool_member(rom, 1))))
    assert [r1.status_code, r2.status_code] == [202, 409]
    assert r2.json()["detail"]["rom_name"] == rom.name
    # The second container stayed free for a player who actually needs one.
    assert free is None


def test_a_session_on_one_platform_does_not_block_a_claim_on_another(
    client, access_token
):
    """The caller's ps2 session sits on a key the ngc walk visits too, and only
    occupies that container rather than counting as the player's ngc session."""
    ps2_rom = _rom_on("ps2")
    ngc_rom = _rom_on("ngc")
    second = _nested(
        host="http://192.168.1.11:3000", broker_host="http://192.168.1.11:8000"
    )
    with _streaming(_nested(), second):
        r1 = _claim_ok(client, access_token, ps2_rom.id)
        r2 = _claim_ok(client, access_token, ngc_rom.id)
    assert [r1.status_code, r2.status_code] == [202, 202]
    assert r1.json()["container"] == _key_of(_nested())
    assert r2.json()["container"] == _key_of(second)


def test_status_does_not_report_a_session_on_another_platform(client, access_token):
    """The ps2 claim shares its key with the container's ngc row, and a poll for
    ngc must not read that as a session the caller holds there."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        assert _claim_ok(client, access_token, ps2_rom.id).status_code == 202
        r = client.get(
            "/api/streaming/sessions/ngc/status", headers=_auth(access_token)
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


@contextmanager
def _claim_in_flight(platform: str, user_id: int) -> Iterator[None]:
    """Stand in for a claim from the same player that is inside the reserve and
    has not put its session on a container key yet."""
    key = session_store._claim_gate_redis_key(platform, user_id)
    assert asyncio.run(
        async_cache.set(key, "1", nx=True, ex=session_store._CLAIM_GATE_TTL_SECONDS)
    )
    try:
        yield
    finally:
        asyncio.run(async_cache.delete(key))


def test_a_pool_refuses_a_claim_racing_one_from_the_same_player(
    client, access_token, admin_user: User, rom: Rom
):
    """Reserving is atomic per container, not across a pool: two claims racing
    would each read no session of their own and win a different member."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        with _claim_in_flight(rom.platform_slug, admin_user.id):
            r = _claim_ok(client, access_token, rom.id)
        held = [
            asyncio.run(session_store.get_session(_key_of(_pool_member(rom, i))))
            for i in (0, 1)
        ]
    assert r.status_code == 409
    # Nothing reserved, so the racing claim still has the whole pool to win.
    assert held == [None, None]


def test_a_pool_hands_the_owner_of_a_stale_session_their_own_container_back(
    client, access_token, rom: Rom
):
    """A crashed tab leaves the owner holding a container nothing refreshes, and
    claiming again takes that one back rather than reserving a second."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _age_session_on(
            _pool_member(rom, 0), session_store._STREAMING_SESSION_STALE_SECONDS + 60
        )
        with _stub_stop():
            r2 = _claim_ok(client, access_token, rom.id)
        free = asyncio.run(session_store.get_session(_key_of(_pool_member(rom, 1))))
    assert r2.status_code == 202
    assert r2.json()["container"] == _key_of(_pool_member(rom, 0))
    assert free is None


def test_pool_never_evicts_a_stale_session_while_a_container_is_free(
    client, access_token, viewer_access_token, rom: Rom
):
    """Config order is a warm-cache preference, not a licence to displace a
    player: an idle container has to be taken before a stale one is torn down."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _age_session_on(
            _pool_member(rom, 0), session_store._STREAMING_SESSION_STALE_SECONDS + 60
        )
        with _stub_stop() as stop_broker:
            r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert r2.status_code == 202
    assert r2.json()["container"] == _key_of(_pool_member(rom, 1))
    stop_broker.assert_not_called()
    assert _session_raw(_pool_member(rom, 0)) is not None


def test_pool_takes_over_a_stale_session_once_every_container_is_held(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, editor_access_token, rom.id)
        _age_session_on(
            _pool_member(rom, 1), session_store._STREAMING_SESSION_STALE_SECONDS + 60
        )
        with _stub_stop() as stop_broker:
            r3 = _claim_ok(client, viewer_access_token, rom.id)
    assert r3.status_code == 202
    assert r3.json()["container"] == _key_of(_pool_member(rom, 1))
    stop_broker.assert_called_once()


def test_control_routes_follow_the_session_not_the_platform(
    client, access_token, viewer_access_token, rom: Rom
):
    """The second player is on the second container, so their volume call has
    to reach that broker rather than the first one the platform lists."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        with patch(
            "handler.streaming.commands.set_volume", return_value=True
        ) as volume:
            r = _volume(client, viewer_access_token, rom.platform_slug)
    assert r.status_code == 200
    assert volume.call_args[0][0].host == "http://192.168.1.11:3000"


def test_control_route_403s_when_every_session_belongs_to_someone_else(
    client, access_token, viewer_access_token, rom: Rom
):
    """The owner scan finding nothing must not read as "no session here"."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        r = _volume(client, viewer_access_token, rom.platform_slug)
    assert r.status_code == 403


def test_an_admin_controls_the_pools_one_active_session(
    client, access_token, viewer_access_token, rom: Rom
):
    """An admin holds nothing on the platform, so the scan finds nothing of
    theirs and falls back to the session that is actually running."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, viewer_access_token, rom.id)
        with patch(
            "handler.streaming.commands.set_volume", return_value=True
        ) as volume:
            r = _volume(client, access_token, rom.platform_slug)
    assert r.status_code == 200
    assert volume.call_args[0][0].host == "http://192.168.1.10:3000"


def test_an_admin_cannot_guess_which_of_two_sessions_to_control(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    """Two sessions and a path that names neither, so ask rather than pick."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, viewer_access_token, rom.id)
        _claim_ok(client, editor_access_token, rom.id)
        r = _volume(client, access_token, rom.platform_slug)
    assert r.status_code == 409


def test_an_admin_names_which_of_two_sessions_to_control(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, viewer_access_token, rom.id)
        _claim_ok(client, editor_access_token, rom.id)
        with patch(
            "handler.streaming.commands.set_volume", return_value=True
        ) as volume:
            r = _volume(
                client,
                access_token,
                rom.platform_slug,
                params={"container": _key_of(_pool_member(rom, 1))},
            )
    assert r.status_code == 200
    assert volume.call_args[0][0].host == "http://192.168.1.11:3000"


@pytest.mark.parametrize(
    "route, body, command",
    [
        ("volume", {"level": 42}, "set_volume"),
        ("mute", {"mute": True}, "set_mute"),
        ("save-state", {"slot": 1}, "save_state"),
        ("load-state", {"slot": 1}, "load_state"),
        ("swap-disc", {"file_id": 1}, "swap_disc"),
    ],
)
def test_a_control_for_a_replaced_claim_never_reaches_the_broker(
    client, access_token, rom: Rom, route, body, command
):
    """A tab that missed its takeover must not drive the claim that replaced it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch(f"handler.streaming.commands.{command}") as broker:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/{route}",
                json=body,
                params={"claimed_at": "2020-01-01T00:00:00+00:00"},
                headers=_auth(access_token),
            )
    assert r.status_code == 404
    broker.assert_not_called()


def test_admin_release_names_the_container(
    client, access_token, viewer_access_token, editor_access_token, rom: Rom
):
    """`container` is the key GET /streaming/sessions reports, and it must
    release that member and leave the rest of the pool playing."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, viewer_access_token, rom.id)
        _claim_ok(client, editor_access_token, rom.id)
        with _stub_stop():
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={"container": _key_of(_pool_member(rom, 1))},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    assert _session_raw(_pool_member(rom, 1)) is None
    assert _session_raw(_pool_member(rom, 0)) is not None


def test_admin_release_rejects_a_container_that_serves_another_platform(
    client, access_token, rom: Rom
):
    with _streaming(_pool_member(rom, 0)):
        r = client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"container": "http://192.168.9.9:8000"},
            headers=_auth(access_token),
        )
    assert r.status_code == 404


def _in_a_later_ps2_pool() -> dict[str, Any]:
    """A second webstation that disagrees with `_webstation()` on the ps2
    emulator, so it forms a later ps2 pool."""
    return cast(
        dict[str, Any],
        _webstation(
            host="http://192.168.1.11:3000",
            broker_host="http://192.168.1.11:8000",
            platforms={"ps2": "play", "ngc": "dolphin"},
        ),
    )


def test_admin_release_ends_a_session_on_a_container_in_a_later_pool(
    client, access_token
):
    """A game claim never reaches a later pool, but an admin can still end a
    session there by naming the container."""
    later = _in_a_later_ps2_pool()
    with _streaming(_webstation(), later):
        key = _key_of(later)
        assert key not in [c.key for c in containers_for_platform("ps2")]
        assert _desktop(client, access_token, key)[0].status_code == 200
        with _stub_stop():
            r = client.delete(
                "/api/streaming/sessions/ps2",
                params={"container": key},
                headers=_auth(access_token),
            )
        assert r.status_code == 200
        assert r.json()["status"] == "released"
        assert _session_raw(later) is None


def test_heartbeat_naming_the_container_refreshes_a_desktop_in_a_later_pool(
    client, access_token
):
    """The platform's lookup only walks the first pool, so only the named key
    keeps this desktop claim fresh."""
    later = _in_a_later_ps2_pool()
    with _streaming(_webstation(), later):
        key = _key_of(later)
        assert _desktop(client, access_token, key)[0].status_code == 200
        _age_session_on(later, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        r = client.post(
            "/api/streaming/sessions/ps2/heartbeat",
            params={"container": key},
            headers=_auth(access_token),
        )
        session = json.loads(_session_raw(later))
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert not session_store.session_is_stale(session)


def test_heartbeat_naming_a_released_container_reports_ended(client, access_token):
    """A session the caller holds on another of the platform's containers must
    not answer for the named one."""
    later = _in_a_later_ps2_pool()
    with _streaming(_webstation(), later):
        key = _key_of(later)
        assert (
            _desktop(client, access_token, _key_of(_webstation()))[0].status_code == 200
        )
        assert _desktop(client, access_token, key)[0].status_code == 200
        with _stub_stop():
            released = client.delete(
                "/api/streaming/sessions/ps2",
                params={"container": key},
                headers=_auth(access_token),
            )
        assert released.status_code == 200
        r = client.post(
            "/api/streaming/sessions/ps2/heartbeat",
            params={"container": key},
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


def test_heartbeat_naming_a_container_leaves_another_users_session_alone(
    client, access_token, viewer_access_token
):
    later = _in_a_later_ps2_pool()
    with _streaming(_webstation(), later):
        key = _key_of(later)
        assert _desktop(client, access_token, key)[0].status_code == 200
        _age_session_on(later, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        r = client.post(
            "/api/streaming/sessions/ps2/heartbeat",
            params={"container": key},
            headers=_auth(viewer_access_token),
        )
        session = json.loads(_session_raw(later))
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert session_store.session_is_stale(session)


def test_status_finds_the_termination_on_whichever_container_held_it(
    client, access_token, viewer_access_token, rom: Rom
):
    """The tombstone is keyed per container, so the poll has to look past the
    first member of the pool to find the displaced player's notice."""
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        with _stub_stop():
            client.delete(
                "/api/streaming/sessions",
                params={"reason": "maintenance"},
                headers=_auth(access_token),
            )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert r.json()["termination"]["reason"] == "maintenance"


def test_status_does_not_report_a_desktop_notice_to_a_game_poll(client, access_token):
    """One tombstone per container and one room per user, so the poll has to
    scope the notice the same way it scopes the session it looked for."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_webstation()):
        key = _key_of(_webstation())
        assert _desktop(client, access_token, key)[0].status_code == 200
        with _stub_stop():
            ended = client.delete(
                "/api/streaming/sessions/ps2",
                params={"container": key, "reason": "patching the host"},
                headers=_auth(access_token),
            )
        assert ended.status_code == 200
        r = client.get(
            f"/api/streaming/sessions/{ps2_rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert r.json()["termination"] is None


def test_a_desktop_beat_still_learns_why_its_claim_ended(client, access_token):
    """The desktop names its container, which is what puts its own notice in
    scope: nothing else would tell that tab it was taken away."""
    with _streaming(_webstation()):
        key = _key_of(_webstation())
        assert _desktop(client, access_token, key)[0].status_code == 200
        with _stub_stop():
            client.delete(
                "/api/streaming/sessions/ps2",
                params={"container": key, "reason": "patching the host"},
                headers=_auth(access_token),
            )
        r = client.post(
            "/api/streaming/sessions/ps2/heartbeat",
            params={"container": key},
            headers=_auth(access_token),
        )
    assert r.json()["status"] == "ended"
    notice = r.json()["termination"]
    assert notice["reason"] == "patching the host"
    assert notice["desktop"] is True
    assert notice["container"] == key


def test_status_does_not_report_a_notice_from_another_platform(client, access_token):
    """A container serving two platforms files both notices under one key, so
    the ngc session ending is not an answer for the ps2 tab."""
    ngc_rom = _rom_on("ngc")
    with _streaming(_nested()):
        _claim_ok(client, access_token, ngc_rom.id)
        with _stub_stop():
            client.delete(
                "/api/streaming/sessions/ngc",
                params={"reason": "patching the host"},
                headers=_auth(access_token),
            )
        r = client.get(
            "/api/streaming/sessions/ps2/status", headers=_auth(access_token)
        )
        ngc = client.get(
            "/api/streaming/sessions/ngc/status", headers=_auth(access_token)
        )
    assert r.json()["status"] == "ended"
    assert r.json()["termination"] is None
    assert ngc.json()["termination"]["reason"] == "patching the host"


def test_heartbeat_refreshes_the_session_on_the_container_that_holds_it(
    client, access_token, viewer_access_token, rom: Rom
):
    with _streaming(_pool_member(rom, 0), _pool_member(rom, 1)):
        _claim_ok(client, access_token, rom.id)
        _claim_ok(client, viewer_access_token, rom.id)
        _age_session_on(_pool_member(rom, 1), 120)
        before = json.loads(_session_raw(_pool_member(rom, 1)))["last_seen"]
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(viewer_access_token),
        )
        after = json.loads(_session_raw(_pool_member(rom, 1)))["last_seen"]
    assert r.json()["status"] == "active"
    assert after > before


def test_a_container_that_disagrees_on_the_emulator_is_a_later_pool(caplog):
    """Pool members file states and cards in one place, so an entry naming a
    different emulator is a pool of its own rather than a spare container."""
    first = {
        "platform": "ps2",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "emulator": "pcsx2",
    }
    second = {**first, "host": "http://192.168.1.11:3000"}
    second["broker_host"] = "http://192.168.1.11:8000"
    second["emulator"] = "play"
    third = {
        **first,
        "host": "http://192.168.1.12:3000",
        "broker_host": "http://192.168.1.12:8000",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(first, second, third):
            with caplog.at_level(logging.WARNING, logger="romm"):
                pools = pools_for_platform("ps2")
                candidates = containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert [[c.emulator for c in pool] for pool in pools] == [
        ["pcsx2", "pcsx2"],
        ["play"],
    ]
    assert candidates == pools[0]
    # Once per config, not once per lookup.
    assert caplog.text.count("never claimed for a game") == 1
    assert _key_of(second) in caplog.text


def test_a_fresh_process_does_not_repeat_the_later_pool_warning(caplog):
    """Every reaper run is a new RQ job process with nothing memoized."""
    first = {
        "platform": "ps2",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
        "emulator": "pcsx2",
    }
    second = {
        **first,
        "host": "http://192.168.1.11:3000",
        "broker_host": "http://192.168.1.11:8000",
        "emulator": "play",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="romm"):
            with _streaming(first, second):
                containers_for_platform("ps2")
            with _streaming(first, second):
                containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert caplog.text.count("never claimed for a game") == 1


def test_a_lone_container_is_a_pool_of_one(rom: Rom):
    member = _pool_member(rom, 0)
    with _streaming(member):
        pools = pools_for_platform(rom.platform_slug)
    assert [[c.key for c in pool] for pool in pools] == [[_key_of(member)]]


def test_webstation_pool_members_at_different_subfolders_are_still_a_pool(caplog):
    """Same-origin pool members each carry their own subfolder, and a subfolder
    only changes how routes are built, not what the broker can do."""
    first = {
        "platform": "ps2",
        "host": "/streaming",
        "broker_host": "http://192.168.1.10:8000",
        "protocol": "webstation",
        "subfolder": "/streaming",
        "emulator": "pcsx2",
    }
    second = {
        **first,
        "host": "/streaming-2",
        "broker_host": "http://192.168.1.11:8000",
        "subfolder": "/streaming-2",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(first, second):
            with caplog.at_level(logging.WARNING, logger="romm"):
                candidates = containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert [c.broker_host for c in candidates] == [
        "http://192.168.1.10:8000",
        "http://192.168.1.11:8000",
    ]
    assert "never claimed for a game" not in caplog.text


def test_a_proxied_host_disagreeing_with_its_subfolder_cannot_be_claimed(caplog):
    """The broker's absolute room path replaces the one `host` carries, so a
    mount that disagrees would route the player to whoever owns that path."""
    entry = {
        "platform": "ps2",
        "host": "/streaming-2",
        "broker_host": "http://192.168.1.11:8000",
        "protocol": "webstation",
        "subfolder": "/streaming",
        "emulator": "pcsx2",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(entry):
            with caplog.at_level(logging.WARNING, logger="romm"):
                candidates = containers_for_platform("ps2")
                listed = resolve_containers()
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert candidates == []
    # Still resolved, so the fleet view shows the operator what is wrong.
    assert [c.key for c in listed] == [""]
    assert "must be the container's own SUBFOLDER" in caplog.text


def test_a_subfolder_left_to_its_default_is_caught_against_the_mount_path(caplog):
    """The likeliest form of the mistake: a second member proxied at its own
    path with `subfolder` forgotten, which defaults to /streaming."""
    entry = {
        "platform": "ps2",
        "host": "/streaming-2",
        "broker_host": "http://192.168.1.11:8000",
        "protocol": "webstation",
        "emulator": "pcsx2",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(entry):
            with caplog.at_level(logging.WARNING, logger="romm"):
                candidates = containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert candidates == []


def test_a_container_mounted_at_the_root_agrees_with_an_empty_subfolder():
    """SUBFOLDER=/ makes the broker's prefix empty and RomM's subfolder "", and
    a host of "/" is the same mount. Normalization has to see those as equal."""
    entry = {
        "platform": "ps2",
        "host": "/",
        "broker_host": "http://192.168.1.11:8000",
        "protocol": "webstation",
        "subfolder": "/",
        "emulator": "pcsx2",
    }
    with _streaming(entry):
        candidates = containers_for_platform("ps2")
    assert [c.broker_host for c in candidates] == ["http://192.168.1.11:8000"]


def test_a_bare_origin_host_may_differ_from_its_subfolder():
    """A host that is only an origin carries no mount path, so the broker's
    absolute room path lands on it whatever the subfolder says."""
    entry = {
        "platform": "ps2",
        "host": "https://webstation.example.com",
        "broker_host": "http://192.168.1.11:8000",
        "protocol": "webstation",
        "subfolder": "/streaming",
        "emulator": "pcsx2",
    }
    with _streaming(entry):
        candidates = containers_for_platform("ps2")
    assert [c.broker_host for c in candidates] == ["http://192.168.1.11:8000"]


def test_a_cross_origin_mount_path_is_checked_against_the_subfolder(caplog):
    """An absolute URL can carry a mount path too, and the broker's room path
    replaces it exactly as it would on RomM's own origin."""
    entry = {
        "platform": "ps2",
        "host": "https://webstation.example.com/streaming-2",
        "broker_host": "http://192.168.1.11:8000",
        "protocol": "webstation",
        "subfolder": "/streaming",
        "emulator": "pcsx2",
    }
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(entry):
            with caplog.at_level(logging.WARNING, logger="romm"):
                candidates = containers_for_platform("ps2")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert candidates == []
    assert "must be the container's own SUBFOLDER" in caplog.text


def test_webstation_pool_claim_rolls_over_across_different_subfolders(
    client, access_token, viewer_access_token, rom: Rom
):
    """End to end: a second claim on a same-origin webstation pool must reach
    the free member instead of 409ing on the first one being held."""
    first = {
        "platform": rom.platform_slug,
        "host": "/streaming",
        "broker_host": "http://192.168.1.20:8000",
        "protocol": "webstation",
        "subfolder": "/streaming",
    }
    second = {
        **first,
        "host": "/streaming-2",
        "broker_host": "http://192.168.1.21:8000",
        "subfolder": "/streaming-2",
    }
    with _streaming(first, second):
        r1 = _claim_webstation_ok(client, access_token, rom.id)
        r2 = _claim_webstation_ok(client, viewer_access_token, rom.id)
    assert [r1.status_code, r2.status_code] == [202, 202]
    assert r1.json()["container"] == _key_of(first)
    assert r2.json()["container"] == _key_of(second)


def test_the_session_platform_picks_the_config_entry_for_its_container():
    """A container serving several platforms expands into one entry per
    platform under one key, so the admin views must not read an arbitrary one:
    the platform-keyed fields (emulator, card sync) differ between them."""
    with _streaming(_nested()):
        grouped = containers_by_key()
        key = _key_of(_first_container("ps2"))
    assert len(grouped[key]) == 2
    for platform in ("ps2", "ngc"):
        entry = container_for_session(grouped, key, platform)
        assert entry is not None
        assert entry.platform == platform
    # A session predating the platform field still resolves to a real entry.
    assert container_for_session(grouped, key, None) is not None
    assert container_for_session(grouped, "http://nope:8000", "ps2") is None


# ── Container names ───────────────────────────────────────────────────────────


def _labelled(label: str | None, index: int) -> dict[str, Any]:
    """A webstation container on its own host, with the given label."""
    return {
        "host": f"http://192.168.1.{index}:3000",
        "broker_host": f"http://192.168.1.{index}:8000",
        "protocol": "webstation",
        "platforms": {"ps2": "pcsx2"},
        **({"label": label} if label is not None else {}),
    }


def test_a_labelled_container_is_named_by_its_label():
    entry = _labelled("WEBSTATION-DEV", 10)
    with _streaming(entry):
        names = container_names()
        key = key_for_name("WEBSTATION-DEV")
    assert names == {_key_of(entry): "WEBSTATION-DEV"}
    assert key == _key_of(entry)


def test_an_unlabelled_container_is_named_by_its_key():
    entry = _labelled(None, 10)
    with _streaming(entry):
        assert container_names() == {_key_of(entry): _key_of(entry)}


def test_a_name_matches_its_label_in_any_case():
    entry = _labelled("Emulation station", 10)
    with _streaming(entry):
        assert key_for_name("emulation STATION") == _key_of(entry)


def test_a_key_still_names_a_labelled_container():
    """Links from before names existed carry the key."""
    entry = _labelled("WEBSTATION-DEV", 10)
    with _streaming(entry):
        assert key_for_name(_key_of(entry)) == _key_of(entry)


def test_an_unknown_name_matches_nothing():
    with _streaming(_labelled("WEBSTATION-DEV", 10)):
        assert key_for_name("WEBSTATION-OTHER") is None


def test_a_shared_label_names_neither_container(caplog):
    first = _labelled("Webstation", 10)
    second = _labelled("webstation", 11)
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with _streaming(first, second):
            with caplog.at_level(logging.WARNING, logger="romm"):
                names = container_names()
                key = key_for_name("Webstation")
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert names == {_key_of(first): _key_of(first), _key_of(second): _key_of(second)}
    assert key is None
    assert "share the label" in caplog.text


def test_a_label_cannot_take_another_containers_key():
    """A label spelled like another container's key must not redirect it."""
    target = _labelled("Target", 10)
    impostor = _labelled(_key_of(target), 11)
    with _streaming(target, impostor):
        names = container_names()
        key = key_for_name(_key_of(target))
    assert names[_key_of(impostor)] == _key_of(impostor)
    assert key == _key_of(target)


def test_a_label_matching_another_containers_key_in_any_case_names_neither():
    target = _labelled("Target", 10)
    impostor = _labelled(_key_of(target).upper(), 11)
    with _streaming(target, impostor):
        names = container_names()
    assert names[_key_of(impostor)] == _key_of(impostor)


def test_a_label_too_long_for_a_url_names_nothing():
    entry = _labelled("x" * (CONTAINER_NAME_MAX_LENGTH + 1), 10)
    with _streaming(entry):
        assert container_names() == {_key_of(entry): _key_of(entry)}


def test_an_unclaimable_container_has_no_name():
    broken = _labelled("Broken", 10) | {"host": "192.168.1.10:3000", "broker_host": ""}
    with _streaming(broken):
        assert container_names() == {}
        assert key_for_name("Broken") is None


# ── Desktop sessions ──────────────────────────────────────────────────────────


def _webstation(**overrides):
    """A container whose broker speaks the webstation protocol, the only one
    that serves a desktop."""
    return _nested(**{"protocol": "webstation", "label": "Webstation", **overrides})


def _containers(client, token):
    return client.get("/api/streaming/containers", headers=_auth(token))


def _desktop(client, token, container_key: str, url="/streaming/room/abc"):
    """Open a desktop with the broker activation stubbed."""
    with patch(
        "handler.streaming.webstation.activate", return_value={"url": url}
    ) as activate:
        response = client.post(
            "/api/streaming/desktop",
            json={"container": container_key},
            headers=_auth(token),
        )
    return response, activate


def _key_of(container) -> str:
    """The session key a container is claimed under, from either a raw config
    entry or a resolved record."""
    if not isinstance(container, dict):
        return cast(str, container.key)
    protocol = protocol_for(container.get("protocol"), container.get("subfolder"))
    return _derive_broker_host(container, protocol) or ""


def _claim_webstation_ok(client, token, rom_id):
    """Claim a game on a webstation container, whose launch goes through
    activate rather than the per-emulator mods' /launch."""
    with patch(
        "handler.streaming.webstation.activate", return_value={"url": "/room/x"}
    ):
        return _claim(client, token, rom_id)


def test_containers_reports_a_container_that_is_still_saving(
    client, access_token, rom: Rom
):
    """A drain marker has no owner, so the row read as idle while the previous
    session's state was still coming out of the container."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _drain(container)
        rows = _containers(client, access_token).json()["containers"]

    assert rows[0]["draining"] is True
    assert rows[0]["session"] is None


def test_a_desktop_refused_over_a_drain_says_it_is_saving(client, access_token):
    """Nobody holds a draining container, so "in use" names no one and the
    admin needs to hear that waiting is enough."""
    ps2_rom = _rom_on("ps2")
    container = _webstation()
    with _streaming(container):
        _claim_webstation_ok(client, access_token, ps2_rom.id)
        _drain(container)
        response, _ = _desktop(client, access_token, _key_of(container))

    assert response.status_code == 409
    assert response.json()["detail"]["draining"] is True


def test_containers_lists_one_row_per_container(client, access_token):
    """A container serves many platforms but hosts one session, so the fleet
    view counts containers, not the platform rows /config ships."""
    second = _webstation(
        host="http://192.168.1.11:3000", broker_host="http://192.168.1.11:8000"
    )
    with _streaming(_webstation(), second):
        response = _containers(client, access_token)
    assert response.status_code == 200
    rows = response.json()["containers"]
    assert len(rows) == 2
    assert sorted(rows[0]["platforms"]) == ["ngc", "ps2"]
    assert rows[0]["supports_desktop"] is True
    assert rows[0]["session"] is None


def test_containers_reports_a_container_that_can_never_be_claimed(client, access_token):
    """A schemeless host derives no key, so the row says so rather than
    sitting in the list looking idle."""
    with _streaming(_nested(host="192.168.1.10:3000", broker_host="")):
        response = _containers(client, access_token)
    assert response.status_code == 200
    assert response.json()["containers"][0]["configured"] is False


def test_containers_shows_what_is_running(client, access_token):
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        assert _claim_ok(client, access_token, ps2_rom.id).status_code == 202
        response = _containers(client, access_token)
    session = response.json()["containers"][0]["session"]
    assert session["rom_name"] == ps2_rom.name
    assert session["desktop"] is False
    assert session["username"] == "test_admin"


def test_containers_reports_each_containers_name(client, access_token):
    labelled = _webstation(label="WEBSTATION-DEV")
    unlabelled = _webstation(
        label=None,
        host="http://192.168.1.11:3000",
        broker_host="http://192.168.1.11:8000",
    )
    with _streaming(labelled, unlabelled):
        rows = _containers(client, access_token).json()["containers"]
    assert [row["name"] for row in rows] == ["WEBSTATION-DEV", _key_of(unlabelled)]
    assert rows[0]["container"] == _key_of(labelled)


def test_desktop_opens_by_label(client, access_token):
    container = _webstation(label="Emulation station")
    with _streaming(container):
        response, activate = _desktop(client, access_token, "emulation station")
    assert response.status_code == 200
    assert response.json()["container"] == _key_of(container)
    activate.assert_called_once()


def test_desktop_still_opens_by_key(client, access_token):
    container = _webstation(label="WEBSTATION-DEV")
    with _streaming(container):
        response, _ = _desktop(client, access_token, _key_of(container))
    assert response.status_code == 200
    assert response.json()["container"] == _key_of(container)


def test_desktop_refuses_an_unknown_name(client, access_token):
    with _streaming(_webstation(label="WEBSTATION-DEV")):
        response, activate = _desktop(client, access_token, "WEBSTATION-OTHER")
    assert response.status_code == 404
    activate.assert_not_called()


def test_containers_is_admin_only(client, viewer_access_token):
    with _streaming(_webstation()):
        assert _containers(client, viewer_access_token).status_code == 403


def test_desktop_claims_the_named_container(client, access_token):
    """The landing URL activate returns is resolved against the stream host,
    the same way a game claim resolves its room URL."""
    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        response, activate = _desktop(client, access_token, key)
    assert response.status_code == 200
    body = response.json()
    assert body["container"] == key
    assert body["host"] == "http://192.168.1.10:3000/streaming/room/abc"
    assert activate.call_args.kwargs["emulator"] == "desktop"
    # No ROM: the broker registers the desktop with requires_rom False, and
    # sending one would make exit try to sync saves that do not exist.
    assert "rom" not in activate.call_args.kwargs


@pytest.mark.parametrize(
    "room_url",
    ["javascript:alert(1)", "https://evil.example/room", "data:text/html,x"],
)
def test_desktop_ignores_a_room_url_that_leaves_the_container(
    client, access_token, room_url
):
    """The URL is the broker's answer and the browser renders it in an iframe,
    so one that is not on the configured host must not reach the player."""
    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        response, _ = _desktop(client, access_token, key, url=room_url)

    assert response.json()["host"] == "http://192.168.1.10:3000"


def test_desktop_and_a_game_block_each_other(client, access_token):
    """Both claim the same key, which is the point: only one thing can drive
    the container's display."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        assert _desktop(client, access_token, key)[0].status_code == 200
        assert _claim_webstation_ok(client, access_token, ps2_rom.id).status_code == 409

    asyncio.run(async_cache.flushall())

    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        assert _claim_webstation_ok(client, access_token, ps2_rom.id).status_code == 202
        assert _desktop(client, access_token, key)[0].status_code == 409


def test_an_admins_desktop_does_not_block_their_game_claim(client, access_token):
    """A desktop occupies its container, not the platform, so the claim rolls
    onto the free pool member."""
    ps2_rom = _rom_on("ps2")
    second = _webstation(
        host="http://192.168.1.11:3000", broker_host="http://192.168.1.11:8000"
    )
    with _streaming(_webstation(), second):
        assert (
            _desktop(client, access_token, _key_of(_webstation()))[0].status_code == 200
        )
        r = _claim_webstation_ok(client, access_token, ps2_rom.id)
    assert r.status_code == 202
    assert r.json()["container"] == _key_of(second)


def test_an_unnamed_heartbeat_skips_the_callers_desktop(
    client, access_token, viewer_access_token
):
    """An admin playing on one pool member while holding a desktop on another
    beats their game session, not the desktop the walk reaches first."""
    ps2_rom = _rom_on("ps2")
    second = _webstation(
        host="http://192.168.1.11:3000", broker_host="http://192.168.1.11:8000"
    )
    with _streaming(_webstation(), second):
        # The viewer takes the head of the pool, so the admin's game lands on
        # the second member and the desktop gets the head once it is released.
        assert (
            _claim_webstation_ok(client, viewer_access_token, ps2_rom.id).status_code
            == 202
        )
        assert _claim_webstation_ok(client, access_token, ps2_rom.id).json()[
            "container"
        ] == _key_of(second)
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task"),
        ):
            client.delete(
                "/api/streaming/sessions/ps2", headers=_auth(viewer_access_token)
            )
        assert (
            _desktop(client, access_token, _key_of(_webstation()))[0].status_code == 200
        )
        _age_session_on(_webstation(), 120)
        _age_session_on(second, 120)
        desktop_before = json.loads(_session_raw(_webstation()))["last_seen"]
        game_before = json.loads(_session_raw(second))["last_seen"]
        r = client.post(
            "/api/streaming/sessions/ps2/heartbeat", headers=_auth(access_token)
        )
        desktop_after = json.loads(_session_raw(_webstation()))["last_seen"]
        game_after = json.loads(_session_raw(second))["last_seen"]
    assert r.json()["status"] == "active"
    assert game_after > game_before
    assert desktop_after == desktop_before


def test_an_unnamed_release_leaves_the_callers_desktop_alone(client, access_token):
    """Desktop.vue names its container and a game tab never does, so an unnamed
    release must not end the desktop the admin has open."""
    with _streaming(_webstation()):
        key = _key_of(_webstation())
        assert _desktop(client, access_token, key)[0].status_code == 200
        with _stub_stop():
            r = client.delete(
                "/api/streaming/sessions/ps2", headers=_auth(access_token)
            )
        session = asyncio.run(session_store.get_session(key))
    assert r.json()["status"] == "not_found"
    assert session is not None and session["desktop"] is True


def test_an_unnamed_release_leaves_another_platforms_session_alone(
    client, access_token
):
    """The container's ngc row shares a key with the caller's ps2 session, so an
    unnamed ngc release must not end the ps2 game."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        assert _claim_ok(client, access_token, ps2_rom.id).status_code == 202
        with _stub_stop():
            r = client.delete(
                "/api/streaming/sessions/ngc", headers=_auth(access_token)
            )
        session = asyncio.run(session_store.get_session(_key_of(_nested())))
    assert r.json()["status"] == "not_found"
    assert session is not None and session["platform"] == "ps2"


def test_an_unnamed_heartbeat_leaves_another_platforms_session_alone(
    client, access_token
):
    """An ngc tab beating unnamed must not keep the caller's ps2 session on the
    same container alive."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        assert _claim_ok(client, access_token, ps2_rom.id).status_code == 202
        _age_session_on(_nested(), 120)
        before = json.loads(_session_raw(_nested()))["last_seen"]
        r = client.post(
            "/api/streaming/sessions/ngc/heartbeat", headers=_auth(access_token)
        )
        after = json.loads(_session_raw(_nested()))["last_seen"]
    assert r.json()["status"] == "ended"
    assert after == before


def test_desktop_is_admin_only(client, viewer_access_token):
    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        response, _ = _desktop(client, viewer_access_token, key)
    assert response.status_code == 403


def test_desktop_404s_on_a_container_that_is_not_configured(client, access_token):
    with _streaming(_webstation()):
        response, _ = _desktop(client, access_token, "http://192.168.9.9:8000")
    assert response.status_code == 404


def test_desktop_rejects_a_container_without_a_webstation_broker(client, access_token):
    """The per-emulator mods have no activate route to ask for a desktop."""
    with _streaming(_nested()):
        key = _key_of(_first_container("ps2"))
        response, activate = _desktop(client, access_token, key)
    assert response.status_code == 400
    activate.assert_not_called()


def test_desktop_frees_the_claim_when_activation_fails(client, access_token):
    """A wedged claim would lock the container out until the TTL expires."""
    with _streaming(_webstation()):
        container = _first_container("ps2")
        key = _key_of(container)
        with patch(
            "handler.streaming.webstation.activate",
            side_effect=HTTPException(status_code=503, detail="down"),
        ):
            response = client.post(
                "/api/streaming/desktop",
                json={"container": key},
                headers=_auth(access_token),
            )
        assert response.status_code == 503
        assert _session_raw(container) is None


def test_releasing_a_desktop_session_syncs_nothing_to_the_library(client, access_token):
    """No ROM means no saves, no states and no playtime to credit, so teardown
    must stop at stopping the emulator."""
    with _streaming(_webstation()):
        container = _first_container("ps2")
        assert _desktop(client, access_token, _key_of(container))[0].status_code == 200
        with (
            _stub_stop() as stop,
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            response = client.delete(
                f"/api/streaming/sessions/{container.platform}",
                params={"container": _key_of(container)},
                headers=_auth(access_token),
            )
    assert response.status_code == 200
    stop.assert_called_once()
    spawn.assert_not_called()
    assert _session_raw(container) is None


def test_the_admin_session_list_flags_a_desktop(client, access_token):
    """rom_name is null on a desktop session, so the list has to say what it
    is rather than leaving the row blank."""
    with _streaming(_webstation()):
        key = _key_of(_first_container("ps2"))
        assert _desktop(client, access_token, key)[0].status_code == 200
        response = client.get("/api/streaming/sessions", headers=_auth(access_token))
    session = response.json()["sessions"][0]
    assert session["desktop"] is True
    assert session["rom_name"] is None


def test_webstation_capabilities_match_the_platform_table(client, access_token):
    """The webstation broker serves the same slots and the same whole-card route
    as the per-emulator ps2 mod, so nothing about it is special-cased."""
    with _streaming(_webstation()):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.status_code == 200
    rows = {c["platform"]: c["capabilities"] for c in response.json()["containers"]}
    assert rows["ps2"] == streaming.platform_capabilities("ps2")


def _webstation_ps2():
    """The resolved ps2 entry of a webstation container, as the routes see it."""
    with _streaming(_webstation()):
        return _first_container("ps2")


def _webstation_json(body: dict[str, Any]):
    """urlopen stub answering one webstation broker call with `body`."""
    resp = MagicMock()
    resp.__enter__.return_value.read.side_effect = _reads(json.dumps(body).encode())
    return resp


def test_webstation_save_state_posts_under_the_subfolder():
    """The state routes live behind SUBFOLDER like the rest of the protocol,
    not at the bare paths the per-emulator mods serve."""
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "saved", "slot": 10, "saved": True}),
    ) as urlopen:
        assert commands.save_state(_resolved(container), 10) is True
    assert urlopen.call_args.args[0].full_url.endswith(
        "/streaming/api/session/save-state"
    )


def test_webstation_save_state_reports_a_refused_save():
    """The broker answers 200 with saved false when the emulator never acked,
    so the status field is what decides, not the HTTP code."""
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "failed", "slot": 10, "saved": False}),
    ):
        assert commands.save_state(_resolved(container), 10) is False


def test_webstation_load_state_posts_under_the_subfolder():
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "loaded", "slot": 3, "loaded": True}),
    ) as urlopen:
        assert commands.load_state(_resolved(container), 3) is True
    assert urlopen.call_args.args[0].full_url.endswith(
        "/streaming/api/session/load-state"
    )


def test_webstation_load_state_reports_an_empty_slot():
    """Loading a slot that holds no state file is a failed load, not an error."""
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "failed", "slot": 3, "loaded": False}),
    ):
        assert commands.load_state(_resolved(container), 3) is False


def test_webstation_swap_disc_posts_under_the_subfolder():
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "ok", "path": "/library/disc2.chd"}),
    ) as urlopen:
        assert commands.swap_disc(_resolved(container), "/library/disc2.chd") is True
    assert urlopen.call_args.args[0].full_url.endswith(
        "/streaming/api/session/swap-disc"
    )
    assert json.loads(urlopen.call_args.args[0].data) == {"path": "/library/disc2.chd"}


def test_webstation_swap_disc_reports_a_broker_refusal():
    """A non-ok status (a bad path, no live session, an unsupported core) is a
    failed swap, not an error."""
    container = _webstation_ps2()
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        return_value=_webstation_json({"status": "error", "detail": "no session"}),
    ):
        assert commands.swap_disc(_resolved(container), "/library/disc2.chd") is False


def test_swap_disc_broker_has_nothing_to_call_on_a_legacy_container():
    """Only the webstation broker speaks the tray protocol; the per-emulator
    brokers this replaced never learned it."""
    container = _container_for(_rom_on("dc"), broker_host="http://192.168.1.10:8000")
    with patch("handler.streaming.broker.urllib.request.urlopen") as urlopen:
        assert commands.swap_disc(_resolved(container), "/library/disc2.chd") is False
    urlopen.assert_not_called()


# ── Staleness / heartbeat ─────────────────────────────────────────────────────


def _age_session_on(container: dict[str, Any], seconds: int) -> None:
    """Rewrite one container's stored session last_seen to `seconds` ago."""
    key = session_store.session_redis_key(_key_of(container))
    session = _load_session(key)
    session["last_seen"] = (
        datetime.now(timezone.utc) - timedelta(seconds=seconds)
    ).isoformat()
    asyncio.run(async_cache.set(key, json.dumps(session)))


def _age_session(rom: Rom, seconds: int) -> None:
    _age_session_on(_container_for(rom), seconds)


def test_session_is_stale_handles_bad_stamps():
    """Missing or corrupt stamps must count as stale, not wedge the container."""
    assert session_store.session_is_stale({}) is True
    assert session_store.session_is_stale({"last_seen": "not-a-date"}) is True
    fresh = datetime.now(timezone.utc).isoformat()
    assert session_store.session_is_stale({"last_seen": fresh}) is False
    old = (
        datetime.now(timezone.utc)
        - timedelta(seconds=session_store._STREAMING_SESSION_STALE_SECONDS + 1)
    ).isoformat()
    assert session_store.session_is_stale({"last_seen": old}) is True


def test_stale_session_taken_over_on_claim(
    client, access_token, viewer_access_token, rom: Rom
):
    """A claim against a session whose heartbeat stopped must tear the old
    session down (broker stop included) and win the container."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with _stub_stop() as stop_broker:
            r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert r1.status_code == 202
    assert r2.status_code == 202
    stop_broker.assert_called_once()


def test_a_swept_session_is_torn_down_with_its_own_platforms_record(
    client, access_token, viewer_access_token
):
    """An ngc claim sweeping a stale ps2 session on a shared container tears it
    down as pcsx2, since the state and card coming out are that emulator's."""
    ps2_rom = _rom_on("ps2")
    ngc_rom = _rom_on("ngc")
    with _streaming(_nested()):
        _claim_ok(client, access_token, ps2_rom.id)
        _age_session_on(_nested(), session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with (
            patch(
                "handler.streaming.commands.stop", return_value=commands.StopOutcome(3)
            ) as stop,
            patch(
                "handler.streaming.states.pull_state_to_library", new=AsyncMock()
            ) as pull_state,
        ):
            r = _claim_ok(client, viewer_access_token, ngc_rom.id)
    assert r.status_code == 202
    assert stop.call_args.args[0].emulator == "pcsx2"
    assert pull_state.call_args.args[2].emulator == "pcsx2"


def test_the_owner_of_a_stale_session_can_claim_it_again(
    client, access_token, rom: Rom
):
    """A held session bars a second one only while the first is still alive, so
    the owner of a crashed tab can press Play again."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with _stub_stop() as stop_broker:
            r2 = _claim_ok(client, access_token, rom.id)
    assert r2.status_code == 202
    stop_broker.assert_called_once()


def test_takeover_leaves_the_displaced_owner_a_notice(
    client, access_token, viewer_access_token, rom: Rom
):
    """Their tab is still showing the stream. Without the note the picture just
    stops with nothing to explain it."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        owner = _load_session(session_store.session_redis_key(_key_of(container)))[
            "user_id"
        ]
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with _stub_stop():
            _claim_ok(client, viewer_access_token, rom.id)

        notice = asyncio.run(session_store.get_termination(_key_of(container), owner))

    assert notice is not None
    assert notice["reason"] == "abandoned"
    assert notice["rom_id"] == rom.id


def test_taking_over_ones_own_stale_session_pushes_no_notice(
    client, access_token, rom: Rom
):
    """The notice goes to the user, whose only tab is now the one that just
    claimed this container, and it would end that fresh claim."""
    container = _container_for(rom)
    sent: list[str] = []

    async def _capture(user_id: Any, event: str, payload: dict[str, Any]) -> None:
        sent.append(event)

    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with (
            _stub_stop(),
            patch("handler.streaming.session_store.push_to_user", new=_capture),
        ):
            _claim_ok(client, access_token, rom.id)

    assert "streaming:session-ended" not in sent


def test_takeover_aborts_when_the_owner_comes_back_first(
    client, access_token, viewer_access_token, rom: Rom
):
    """The staleness check is older than the teardown it triggers. Re-checking
    under the marker is what stops a returning owner's container being wiped."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)

        real_stale = session_store.session_is_stale
        checked = False

        def stale_then_fresh(session):
            # Stale for the scan that picks the candidate, fresh by the time
            # the teardown re-checks it, as if a heartbeat landed in between.
            nonlocal checked
            if checked:
                return False
            checked = True
            return real_stale(session)

        # Both callers hold their own reference: session_store runs the scan,
        # lifecycle re-checks under the marker.
        with (
            patch.object(session_store, "session_is_stale", stale_then_fresh),
            patch.object(lifecycle, "session_is_stale", stale_then_fresh),
            _stub_stop() as stop_broker,
        ):
            r = _claim_ok(client, viewer_access_token, rom.id)

    assert r.status_code == 409
    stop_broker.assert_not_called()


def test_fresh_session_not_taken_over(
    client, access_token, viewer_access_token, rom: Rom
):
    """A session with a live heartbeat keeps its claim: second claim is 409
    and the running emulator is never stopped."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        with _stub_stop() as stop_broker:
            r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert r1.status_code == 202
    assert r2.status_code == 409
    stop_broker.assert_not_called()


def test_heartbeat_refreshes_last_seen(client, access_token, rom: Rom):
    """A heartbeat on an aged session must reset its staleness clock so a
    rival claim no longer takes it over."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    key = session_store.session_redis_key(_key_of(_container_for(rom)))
    session = _load_session(key)
    assert not session_store.session_is_stale(session)


def test_a_heartbeat_for_a_replaced_claim_reports_ended(client, access_token, rom: Rom):
    """A tab that missed its takeover must not keep the claim that replaced it
    alive: the stamp it was given is what identifies the claim it holds."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, 60)
        before = json.loads(_session_raw(_container_for(rom)))["last_seen"]
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            params={"claimed_at": "2020-01-01T00:00:00+00:00"},
            headers=_auth(access_token),
        )
        after = json.loads(_session_raw(_container_for(rom)))["last_seen"]
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert after == before


def test_a_heartbeat_naming_its_own_claim_still_refreshes_it(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        claimed_at = _claim_ok(client, access_token, rom.id).json()["claimed_at"]
        _age_session(rom, 60)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            params={"claimed_at": claimed_at},
            headers=_auth(access_token),
        )
        session = json.loads(_session_raw(_container_for(rom)))
    assert r.json()["status"] == "active"
    assert not session_store.session_is_stale(session)


def test_heartbeat_racing_a_teardown_reports_ended(client, access_token, rom: Rom):
    """The refresh finds nothing when the claim was released between the lookup
    and the write; answering "active" there would leave the client beating a
    session it no longer holds."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        key = session_store.session_redis_key(_key_of(container))

        real_find = access.find_session_for_user

        async def find_then_drop(*args, **kwargs):
            found = await real_find(*args, **kwargs)
            await async_cache.delete(key)
            return found

        with patch.object(access, "find_session_for_user", find_then_drop):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


def test_heartbeat_for_a_session_reassigned_mid_request_reports_ended(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """The write re-checks the owner the lookup found: a takeover landing in
    between must not have the loser's beat keep it alive."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, 60)
        before = json.loads(_session_raw(container))["last_seen"]
        key = session_store.session_redis_key(_key_of(container))

        real_find = access.find_session_for_user

        async def find_then_reassign(*args, **kwargs):
            found = await real_find(*args, **kwargs)
            raw = await async_cache.get(key)
            assert raw is not None
            session = json.loads(raw)
            session["user_id"] = viewer_user.id
            await async_cache.set(key, json.dumps(session))
            return found

        with patch.object(access, "find_session_for_user", find_then_reassign):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
                headers=_auth(access_token),
            )
        after = json.loads(_session_raw(container))["last_seen"]
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert after == before


def test_heartbeat_for_a_claim_restamped_mid_request_reports_ended(
    client, access_token, rom: Rom
):
    """The same player pressing Play again between the lookup and the write
    replaces the claim, which the old tab's beat must not keep alive."""
    container = _container_for(rom)
    with _streaming(container):
        claimed_at = _claim_ok(client, access_token, rom.id).json()["claimed_at"]
        _age_session(rom, 60)
        before = json.loads(_session_raw(container))["last_seen"]
        key = session_store.session_redis_key(_key_of(container))

        real_find = access.find_session_for_user

        async def find_then_restamp(*args, **kwargs):
            found = await real_find(*args, **kwargs)
            raw = await async_cache.get(key)
            assert raw is not None
            session = json.loads(raw)
            session["claimed_at"] = "2099-01-01T00:00:00+00:00"
            await async_cache.set(key, json.dumps(session))
            return found

        with patch.object(access, "find_session_for_user", find_then_restamp):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
                params={"claimed_at": claimed_at},
                headers=_auth(access_token),
            )
        after = json.loads(_session_raw(container))["last_seen"]
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert after == before


def test_heartbeat_does_not_revive_a_draining_session(client, access_token, rom: Rom):
    """A container being torn down must not be made to look live again: the
    emulator is already stopped and its card evacuated."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        key = session_store.session_redis_key(_key_of(container))
        session = _load_session(key)
        session["draining"] = True
        asyncio.run(async_cache.set(key, json.dumps(session)))

        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


def test_heartbeat_keeps_a_disc_swap_that_landed_first(client, access_token, rom: Rom):
    """Heartbeat and swap rewrite the same session blob. Writing back the copy
    read at the start of the request would drop the disc the swap just set."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        session_key = _key_of(container)
        key = session_store.session_redis_key(session_key)

        real_find = access.find_session_for_user

        async def find_then_swap(*args, **kwargs):
            # The swap lands after the heartbeat read its copy of the session.
            found = await real_find(*args, **kwargs)
            await session_store.set_session_disc(session_key, 4242)
            return found

        with patch.object(access, "find_session_for_user", find_then_swap):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
                headers=_auth(access_token),
            )
        session = _load_session(key)

    assert r.json()["status"] == "active"
    assert session["disc_file_id"] == 4242
    assert not session_store.session_is_stale(session)


def test_each_disc_swap_is_kept_in_the_session_history(rom: Rom):
    container = _container_for(rom)
    session_key = _key_of(container)
    key = session_store.session_redis_key(session_key)
    sync_cache.set(key, json.dumps({"rom_id": rom.id}))

    async def swap_twice() -> None:
        await session_store.set_session_disc(session_key, 41)
        await session_store.set_session_disc(session_key, 42)

    asyncio.run(swap_twice())
    session = _load_session(key)

    assert session["disc_file_id"] == 42
    swaps = session_store.session_disc_swaps(session)
    assert [swap.file_id for swap in swaps] == [41, 42]
    assert swaps[0].at <= swaps[1].at


def test_heartbeat_without_session_reports_ended(client, access_token, rom: Rom):
    """No session at all still answers 200/ended: the poll is how a player
    learns their stream is gone, so it must not look like a route error."""
    with _streaming(_container_for(rom)):
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"
    assert r.json()["termination"] is None


def test_heartbeat_by_other_user_reports_ended(
    client, access_token, viewer_access_token, rom: Rom
):
    """A non-owner's heartbeat must not refresh or 403 the session; it just
    reports that the caller does not hold it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


def test_heartbeat_for_unknown_platform_returns_404(client, access_token, rom: Rom):
    with _streaming(_container_for(rom)):
        r = client.post(
            "/api/streaming/sessions/not-a-platform/heartbeat",
            headers=_auth(access_token),
        )
    assert r.status_code == 404


# ── Session status / termination notices ──────────────────────────────────────


def test_status_reports_active_for_owner(client, access_token, rom: Rom):
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json() == {
        "status": "active",
        "platform": rom.platform_slug,
        "extraction_phase": None,
        "termination": None,
        "host": container["host"],
        "core": None,
        "core_tier": None,
    }


def test_status_carries_the_room_the_launch_answered_with(client, access_token):
    """launch-ready is pushed once: a tab that was reloading when the game came
    up has only the poll to find its way back into the stream."""
    rom = _rom_on("ps2")
    container = _webstation()
    with _streaming(container):
        assert _claim_webstation_ok(client, access_token, rom.id).status_code == 202
        r = client.get(
            "/api/streaming/sessions/ps2/status", headers=_auth(access_token)
        )
    assert r.status_code == 200
    assert r.json()["host"].endswith("/room/x")


def test_a_desktop_launch_is_stamped_without_a_room(client, access_token):
    """The desktop POST is the only place its room is read, so the session keeps
    just the launch stamp the status fallback gates its broker call on."""
    container = _webstation()
    with _streaming(container):
        response, _ = _desktop(client, access_token, _key_of(container))
        assert response.status_code == 200
        session = json.loads(_session_raw(container))
    assert session["launched_at"]
    assert "host" not in session


def test_status_does_not_refresh_the_session(client, access_token, rom: Rom):
    """Status is read-only: polling it must not extend a claim, otherwise a
    background tab could keep a container hostage without playing."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    key = session_store.session_redis_key(_key_of(_container_for(rom)))
    session = _load_session(key)
    assert session_store.session_is_stale(session)


def test_status_for_a_replaced_claim_reports_ended(client, access_token, rom: Rom):
    """A loading tab whose claim was re-taken on the same container must not be
    handed the new claim's room as its own."""
    with _streaming(_container_for(rom)):
        first = _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        with _stub_stop():
            second = _claim_ok(client, access_token, rom.id)
        assert second.json()["container"] == first.json()["container"]
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            params={"claimed_at": first.json()["claimed_at"]},
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ended"


def test_admin_release_leaves_termination_notice(
    client, access_token, viewer_access_token, rom: Rom
):
    """The displaced player's next poll must name who ended the session and
    why, since nothing about the dead stream itself says so."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        released = client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "maintenance window"},
            headers=_auth(access_token),
        )
        assert released.status_code == 200
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ended"
    assert body["termination"]["reason"] == "maintenance window"
    assert body["termination"]["ended_by"]


def test_admin_release_notifies_the_displaced_player(
    client, access_token, viewer_access_token, admin_user, viewer_user, rom: Rom
):
    """The note expires with the claim, so the player who had no tab open when
    an admin ended their game hears of it from a notification instead."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "maintenance window"},
            headers=_auth(access_token),
        )

    [notification] = db_notification_handler.get_notifications(viewer_user.id)
    assert notification.kind == NotificationKind.STREAMING_SESSION_ENDED
    assert notification.actor_id == admin_user.id
    assert notification.data["rom_id"] == rom.id
    assert notification.data["reason"] == "maintenance window"
    assert db_notification_handler.get_notifications(admin_user.id) == []


def test_heartbeat_carries_termination_notice(
    client, access_token, viewer_access_token, rom: Rom
):
    """The heartbeat is the poll a player is already making, so it must carry
    the same notice as the status route: that is the path a force-released
    browser actually learns the reason on."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "patching the host"},
            headers=_auth(access_token),
        )
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ended"
    assert body["termination"]["reason"] == "patching the host"


def test_a_termination_notice_names_the_container_it_ended(
    client, access_token, viewer_access_token, rom: Rom
):
    """A player can hold a session on several containers, so the notice has to
    say which one ended for the right tab to act on it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "maintenance window"},
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    notice = r.json()["termination"]
    assert notice["container"] == _key_of(_container_for(rom))
    assert notice["desktop"] is False


def test_a_termination_notice_names_the_claim_it_ended(
    client, access_token, viewer_access_token, rom: Rom
):
    """A re-claim of the same container keeps its key, so only the stamp tells
    the tab that lost its claim from the one holding the next."""
    with _streaming(_container_for(rom)):
        claimed_at = _claim_ok(client, viewer_access_token, rom.id).json()["claimed_at"]
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    assert r.json()["termination"]["claimed_at"] == claimed_at


def test_status_does_not_report_the_notice_of_another_claim(
    client, access_token, viewer_access_token, rom: Rom
):
    """A poll names the claim it asks about, so a notice filed for another
    claim on the container must not tell it who ended its own."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "maintenance window"},
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            params={"claimed_at": "2026-09-17T10:05:00+00:00"},
            headers=_auth(viewer_access_token),
        )
    assert r.json()["status"] == "ended"
    assert r.json()["termination"] is None


def test_a_termination_notice_lands_before_the_drain(
    client, access_token, viewer_access_token, rom: Rom
):
    """The session ends when the drain marker is written, so a poll during the
    seconds-long drain is told why the stream stopped, not a bare `ended`."""
    container = _container_for(rom)
    seen: list[dict[str, Any] | None] = []

    with _streaming(container):
        _claim_ok(client, viewer_access_token, rom.id)
        user_id = json.loads(_session_raw(container))["user_id"]

        async def capture(*args, **kwargs):
            seen.append(
                await session_store.get_termination(_key_of(container), user_id)
            )
            return commands.StopOutcome()

        with patch(
            "handler.streaming.lifecycle.quiesce_container",
            new=AsyncMock(side_effect=capture),
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={"reason": "maintenance window"},
                headers=_auth(access_token),
            )
    assert seen and seen[0] is not None
    assert seen[0]["reason"] == "maintenance window"


def test_a_takeover_notice_lands_before_the_drain(
    client, access_token, viewer_access_token, rom: Rom
):
    """The abandoned owner's tab polls through the takeover's drain like any
    other, so the notice has to be there before the quiesce starts."""
    container = _container_for(rom)
    seen: list[dict[str, Any] | None] = []

    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        owner = json.loads(_session_raw(container))["user_id"]
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)

        async def capture(*args, **kwargs):
            seen.append(await session_store.get_termination(_key_of(container), owner))
            return commands.StopOutcome()

        with patch(
            "handler.streaming.lifecycle.quiesce_container",
            new=AsyncMock(side_effect=capture),
        ):
            _claim_ok(client, viewer_access_token, rom.id)
    assert seen and seen[0] is not None
    assert seen[0]["reason"] == "abandoned"


def test_force_release_all_leaves_termination_notice(
    client, access_token, viewer_access_token, rom: Rom
):
    """The sweep is the other admin path out of a session, so it must leave the
    same notice as the platform-keyed release."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        swept = client.delete(
            "/api/streaming/sessions",
            params={"reason": "server restart"},
            headers=_auth(access_token),
        )
        assert swept.status_code == 200
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    assert r.json()["termination"]["reason"] == "server restart"


def test_self_release_leaves_no_termination_notice(
    client, access_token, admin_user, rom: Rom
):
    """A user who closed their own session already knows why it stopped. The
    player's own release path sends no reason, which is what marks it as such."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    assert r.json()["termination"] is None
    assert db_notification_handler.get_notifications(admin_user.id) == []


def test_admin_release_of_own_session_leaves_notice(client, access_token, rom: Rom):
    """An admin can be logged in as the account that is playing in another tab,
    so a panel release must still notify: only that path sends the reason
    param, which is how it is told apart from the player closing their game."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "clearing the container"},
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    body = r.json()
    assert body["status"] == "ended"
    assert body["termination"]["reason"] == "clearing the container"
    assert body["termination"]["ended_by"]


def test_admin_release_with_blank_reason_still_names_the_admin(
    client, access_token, viewer_access_token, rom: Rom
):
    """The panel sends the param even when the field is left empty, so the
    player is still told who ended it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": ""},
            headers=_auth(access_token),
        )
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(viewer_access_token),
        )
    body = r.json()
    assert body["termination"]["ended_by"]
    assert body["termination"]["reason"] is None


def test_reclaim_clears_termination_notice(
    client, access_token, viewer_access_token, rom: Rom
):
    """Once the player is back in a session the old notice is spent, so a
    later poll must not resurface it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            params={"reason": "maintenance window"},
            headers=_auth(access_token),
        )
        _claim_ok(client, viewer_access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(viewer_access_token),
        )
    assert r.json()["status"] == "active"


# ── Launch progress ───────────────────────────────────────────────────────────


def _unstamp_launch(container: dict[str, Any]) -> None:
    """Drop the launched_at stamp, leaving the record in the state a claim
    holds while its activate is still running."""
    key = session_store.session_redis_key(_key_of(container))
    session = _load_session(key)
    session.pop("launched_at", None)
    asyncio.run(async_cache.set(key, json.dumps(session)))


def test_status_reports_the_extraction_phase_during_a_launch(client, access_token):
    """The claim blocks through a pkg unpack, so this poll is the only thing the
    waiting player has to look at."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_webstation()):
        _claim_webstation_ok(client, access_token, ps2_rom.id)
        _unstamp_launch(_first_container("ps2"))
        with patch(
            "handler.streaming.broker.request_safe",
            return_value={"extraction_phase": "extracting_pkg"},
        ):
            r = client.get(
                "/api/streaming/sessions/ps2/status", headers=_auth(access_token)
            )
    assert r.status_code == 200
    assert r.json()["extraction_phase"] == "extracting_pkg"


def test_status_reports_no_phase_before_the_broker_starts_unpacking(
    client, access_token
):
    """A launch with no extraction step, or one polled before it reaches the
    unpack, answers with nothing rather than a stale phase."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_webstation()):
        _claim_webstation_ok(client, access_token, ps2_rom.id)
        _unstamp_launch(_first_container("ps2"))
        with patch(
            "handler.streaming.broker.request_safe", return_value={"active": True}
        ):
            r = client.get(
                "/api/streaming/sessions/ps2/status", headers=_auth(access_token)
            )
    assert r.json()["extraction_phase"] is None


def test_status_stops_asking_the_broker_once_the_launch_returned(client, access_token):
    """This poll runs for the life of the session, so past the launch it has to
    stay a pure Redis read rather than a broker round trip per tick."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_webstation()):
        _claim_webstation_ok(client, access_token, ps2_rom.id)
        with patch("handler.streaming.broker.request_safe") as broker:
            r = client.get(
                "/api/streaming/sessions/ps2/status", headers=_auth(access_token)
            )
    assert r.json()["status"] == "active"
    assert r.json()["extraction_phase"] is None
    broker.assert_not_called()


def test_status_on_a_legacy_container_never_asks_for_a_phase(
    client, access_token, rom: Rom
):
    """Only the webstation broker has an extraction step. The per-emulator mods
    have no /status route to ask, so a claim of theirs must not reach for one."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _unstamp_launch(_container_for(rom))
        with patch("handler.streaming.broker.request_safe") as broker:
            r = client.get(
                f"/api/streaming/sessions/{rom.platform_slug}/status",
                headers=_auth(access_token),
            )
    assert r.json()["status"] == "active"
    assert r.json()["extraction_phase"] is None
    broker.assert_not_called()


# ── Release / ownership ───────────────────────────────────────────────────────


def test_release_uses_container_key_not_platform(client, access_token, rom: Rom):
    """release_session must find the session by broker_host, not platform string."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with _stub_stop():
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"


def test_a_release_for_a_replaced_claim_leaves_the_session(
    client, access_token, rom: Rom
):
    """A tab whose claim was taken over still releases on unload, and it must
    not end the session that replaced it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with _stub_stop() as stop:
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={"claimed_at": "2020-01-01T00:00:00+00:00"},
                headers=_auth(access_token),
            )
        session = asyncio.run(session_store.get_session(_key_of(_container_for(rom))))
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    stop.assert_not_called()
    assert session is not None


def test_a_release_naming_its_own_claim_still_ends_the_session(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        claimed_at = _claim_ok(client, access_token, rom.id).json()["claimed_at"]
        with _stub_stop() as stop:
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={"claimed_at": claimed_at},
                headers=_auth(access_token),
            )
    assert r.json()["status"] == "released"
    stop.assert_called_once()


def test_a_release_for_a_claim_another_player_took_over_is_a_no_op(
    client, viewer_access_token, editor_access_token, rom: Rom
):
    """The tab lost its claim, so the player now holding the container is none
    of its business, not a forbidden target."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, editor_access_token, rom.id)
        with _stub_stop() as stop:
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={
                    "container": _key_of(_container_for(rom)),
                    "claimed_at": "2020-01-01T00:00:00+00:00",
                },
                headers=_auth(viewer_access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    stop.assert_not_called()


def test_an_unnamed_release_for_a_claim_another_player_took_over_is_a_no_op(
    client, viewer_access_token, editor_access_token, rom: Rom
):
    """A stamped release that names no container reads a takeover the same way
    as a named one."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, editor_access_token, rom.id)
        with _stub_stop() as stop:
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                params={"claimed_at": "2020-01-01T00:00:00+00:00"},
                headers=_auth(viewer_access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    stop.assert_not_called()


def test_release_by_other_user_is_forbidden(
    client, access_token, viewer_access_token, rom: Rom
):
    """A session claimed by one user cannot be released by another non-admin."""
    with _streaming(_container_for(rom)):
        # viewer claims the session; admin could override, a viewer cannot
        r_claim = _claim_ok(client, access_token, rom.id)
        r = client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            headers=_auth(viewer_access_token),
        )
    assert r_claim.status_code == 202
    assert r.status_code == 403


def test_save_state_by_other_user_is_forbidden(
    client, access_token, viewer_access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/save-state",
            json={"slot": 1},
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 403


async def _run_spawned(tasks: list[object]) -> None:
    """Run what the route handed to the mocked _spawn_sync_task."""
    for task in tasks:
        if asyncio.iscoroutine(task):
            await task


def _spawns_nothing():
    """Close the spawned coroutine, which a bare MagicMock would leave unawaited."""
    return patch(
        "handler.streaming.background.spawn_sync_task",
        side_effect=lambda coro: coro.close(),
    )


def test_save_and_exit_releases_session_once_the_state_is_pulled(
    client, access_token, rom: Rom
):
    """The broker keeps the exited session's state only until the next
    activate, so the claim holds while the pull runs and goes when it lands."""
    spawned: list[object] = []
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 10, True),
            ),
            patch("handler.streaming.states.pull_state_to_library", new=AsyncMock()),
            patch("handler.streaming.saves.pull_saves_to_library", new=AsyncMock()),
            patch(
                "handler.streaming.background.spawn_sync_task",
                side_effect=spawned.append,
            ),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
            # Still held: the state has not come back out of the container yet.
            held = _claim_ok(client, access_token, rom.id)
            asyncio.run(_run_spawned(spawned))
        r2 = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert held.status_code == 409
    assert r2.status_code == 202


def test_a_save_and_exit_for_a_replaced_claim_leaves_the_session(
    client, access_token, rom: Rom
):
    """A playing tab that missed its takeover saves and exits on unload, and
    must not end the session that replaced it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(False, 10, False),
        ) as save_and_exit:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                params={
                    "container": _key_of(_container_for(rom)),
                    "claimed_at": "2020-01-01T00:00:00+00:00",
                },
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
        session = asyncio.run(session_store.get_session(_key_of(_container_for(rom))))
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    save_and_exit.assert_not_called()
    assert session is not None


def test_a_save_and_exit_naming_its_own_claim_still_ends_the_session(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        claimed_at = _claim_ok(client, access_token, rom.id).json()["claimed_at"]
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(False, 10, False),
        ) as save_and_exit:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                params={
                    "container": _key_of(_container_for(rom)),
                    "claimed_at": claimed_at,
                },
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
    assert r.json()["status"] == "ok"
    save_and_exit.assert_called_once()


def test_a_named_save_and_exit_leaves_another_platforms_session_alone(
    client, access_token
):
    """The container's ngc row shares a key with the caller's ps2 session, so a
    named ngc save-and-exit must not save and kill the ps2 game."""
    ps2_rom = _rom_on("ps2")
    with _streaming(_nested()):
        assert _claim_ok(client, access_token, ps2_rom.id).status_code == 202
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(True, 10, True),
        ) as save_and_exit:
            r = client.post(
                "/api/streaming/sessions/ngc/save-and-exit",
                params={"container": _key_of(_nested())},
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
        session = asyncio.run(session_store.get_session(_key_of(_nested())))
    assert r.json()["status"] == "not_found"
    save_and_exit.assert_not_called()
    assert session is not None and session["platform"] == "ps2"


def test_a_named_save_and_exit_leaves_a_desktop_alone(client, access_token):
    """Save-and-exit acts on a game, so naming a desktop's container reaches
    nothing to save."""
    container = _webstation()
    key = _key_of(container)
    with _streaming(container):
        assert _desktop(client, access_token, key)[0].status_code == 200
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(True, 10, True),
        ) as save_and_exit:
            r = client.post(
                "/api/streaming/sessions/ps2/save-and-exit",
                params={"container": key},
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
        session = asyncio.run(session_store.get_session(key))
    assert r.json()["status"] == "not_found"
    save_and_exit.assert_not_called()
    assert session is not None and session["desktop"] is True


def test_a_save_and_exit_with_nothing_active_is_a_no_op(client, access_token, rom: Rom):
    """A retried unload finds its claim already gone, which ends nothing."""
    with _streaming(_container_for(rom)):
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(False, 10, False),
        ) as save_and_exit:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    assert r.json()["released"] is True
    save_and_exit.assert_not_called()


def test_save_and_exit_failure_still_releases_session(client, access_token, rom: Rom):
    """A failed save is reported as saved=False, but the session is still
    released - the container must not stay claimed by a dead session."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(False, 10, False),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
        r2 = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is False
    assert r2.status_code == 202


def test_save_and_exit_rejects_a_slot_the_platform_lacks(client, access_token):
    """The exit save writes to a slot like any other save, so a slot the
    platform does not expose is refused here too rather than at the broker."""
    rom = _rom_on("ngc")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch(
            "handler.streaming.commands.save_and_exit",
            return_value=commands.SaveAndExitOutcome(True, 9, True),
        ) as broker:
            r = client.post(
                "/api/streaming/sessions/ngc/save-and-exit",
                json={"slot": 9, "wait": True},
                headers=_auth(access_token),
            )
    assert r.status_code == 422
    broker.assert_not_called()


def test_force_release_all_stops_brokers(client, access_token, rom: Rom):
    """Force-release must tell each broker to stop, not just clear Redis."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with _stub_stop() as stop_broker:
            r = client.delete("/api/streaming/sessions", headers=_auth(access_token))
    assert r.status_code == 200
    assert stop_broker.call_count == 1


# ── Save-state sync ───────────────────────────────────────────────────────────


def test_save_state_rejects_slot_above_platform_max(client, access_token):
    """Dolphin's slots stop at the autosave (8); slot 9 clears the coarse union
    bound (<=10) but must be rejected against the platform's real ceiling."""
    rom = _rom_on("ngc")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            "/api/streaming/sessions/ngc/save-state",
            json={"slot": 9},
            headers=_auth(access_token),
        )
    assert r.status_code == 422


def test_save_state_allows_platform_autosave_slot(client, access_token):
    """The player writes through the autosave slot, so it is a valid target."""
    rom = _rom_on("ngc")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.save_state", return_value=True):
            r = client.post(
                "/api/streaming/sessions/ngc/save-state",
                json={"slot": 8},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["slot"] == 8


def test_load_state_allows_platform_autosave_slot(client, access_token):
    """Dolphin's slot 8 is not manually savable but is loadable as the autosave."""
    rom = _rom_on("wii")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.load_state", return_value=True):
            r = client.post(
                "/api/streaming/sessions/wii/load-state",
                json={"slot": 8},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["loaded"] is True


def test_load_state_rejects_slot_between_max_and_autosave(client, access_token):
    """Dolphin: slot 9 is neither a manual slot (1-7) nor the autosave (8)."""
    rom = _rom_on("ngc")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            "/api/streaming/sessions/ngc/load-state",
            json={"slot": 9},
            headers=_auth(access_token),
        )
    assert r.status_code == 422


def _state_fields(rom: Rom, emulator: str) -> dict[str, Any]:
    return {
        "emulator": emulator,
        "file_path": f"{rom.platform_slug}/states/{emulator}",
        "file_size_bytes": 1.0,
    }


def _state_for(rom: Rom, user: User, file_name: str, emulator: str) -> State:
    """An unsaved state, as a patched scan_state returns one."""
    return State(
        rom_id=rom.id,
        user_id=user.id,
        file_name=file_name,
        **_state_fields(rom, emulator),
    )


def _add_state(
    rom: Rom, user: User, file_name: str, emulator: str, **overrides: Any
) -> State:
    return make_state(
        rom, user, file_name, **(_state_fields(rom, emulator) | overrides)
    )


def _core_state(rom: Rom, user: User, file_name: str, core: str | None) -> State:
    """A stored RetroArch state recorded as written by `core`."""
    return _add_state(rom, user, file_name, "retroarch", core=core)


def test_a_state_keeps_the_core_that_wrote_it(rom: Rom, admin_user: User):
    stored = _core_state(rom, admin_user, "Game.state", "bsnes")
    reread = db_state_handler.get_state_by_id(stored.id)
    assert reread is not None and reread.core == "bsnes"
    assert StateSchema.model_fields["core"].default is None


def _screenshot_for(rom: Rom, stem: str) -> Screenshot:
    """A scan_screenshot() stand-in on `stem`, the name State.screenshot matches."""
    return Screenshot(
        file_name=f"{stem}.png",
        file_name_no_tags=stem,
        file_name_no_ext=stem,
        file_extension="png",
        file_path=f"{rom.platform_slug}/screenshots",
        file_size_bytes=7,
    )


def _written_screenshot(write_file: AsyncMock) -> bytes:
    """The bytes stored under the state's .png, from a patched write_file."""
    calls = [
        c for c in write_file.await_args_list if c.kwargs["filename"].endswith(".png")
    ]
    assert len(calls) == 1, "expected exactly one screenshot write"
    return cast(bytes, calls[0].kwargs["file"])


def test_claim_spawns_state_hydration(client, access_token, rom: Rom):
    """Claiming a session must schedule a background hydration of the
    container's save-state slots from the user's stored states."""
    with _streaming(_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.states.hydrate_states_to_broker", new=MagicMock()
            ) as hydrate,
        ):
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    spawn.assert_called_once()
    assert hydrate.call_args[0][1] == rom.id


def test_save_state_spawns_library_pull(client, access_token):
    """Every manual save-state must schedule a background pull to the library."""
    rom = _rom_on("ps2")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("handler.streaming.commands.save_state", return_value=True),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.states.pull_state_to_library", new=MagicMock()
            ) as pull,
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-state",
                json={"slot": 3},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    spawn.assert_called_once()
    _, pulled_rom_id, _, pulled_slot = pull.call_args[0]
    assert pulled_rom_id == rom.id
    assert pulled_slot == 3


def test_save_and_exit_pulls_broker_effective_slot(client, access_token, rom: Rom):
    """The state pull must target the slot the broker actually saved to (slot 0
    is resolved broker-side to its exit-save slot), not the requested slot. The
    in-game save pull is spawned alongside it."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 10, True),
            ),
            _spawns_nothing() as spawn,
            patch(
                "handler.streaming.states.pull_state_to_library", new=MagicMock()
            ) as pull,
            patch("handler.streaming.saves.pull_saves_to_library", new=AsyncMock()),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    # One spawn for the state pull, one for the in-game save pull.
    assert spawn.call_count == 2
    assert pull.call_args[0][3] == 10


def test_save_and_exit_failed_blocking_save_skips_state_pull(
    client, access_token, rom: Rom
):
    """A confirmed-failed blocking save has no state to pull, but in-game saves
    are still synced (memory cards flush during play, not on the savestate)."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(False, 10, False),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.states.pull_state_to_library", new=MagicMock()
            ) as state_pull,
            patch(
                "handler.streaming.saves.pull_saves_to_library",
                new_callable=AsyncMock,
            ) as save_pull,
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
            spawn.assert_called_once()
            asyncio.run(spawn.call_args[0][0])
    assert r.status_code == 200
    state_pull.assert_not_called()
    save_pull.assert_awaited_once()


def test_save_and_exit_holds_the_container_until_the_state_is_pulled(
    client, access_token, rom: Rom
):
    """A session with a rom always has an exit state to collect, so the key is
    replaced by the marker that guards the pull rather than deleted: a re-claim
    landing first would let the container overwrite the state on its next
    launch. The marker is refreshed while the pull runs, so it only has to
    outlive one refresh interval."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 10, True),
            ),
            patch("handler.streaming.states.pull_state_to_library", new=MagicMock()),
            patch("handler.streaming.saves.pull_saves_to_library", new=AsyncMock()),
            _spawns_nothing(),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": False},
                headers=_auth(access_token),
            )
        # The drain key briefly holds the container.
        r2 = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    # Re-claim during the drain window is rejected (409), not accepted (200).
    assert r2.status_code == 409
    # Nobody holds the container, so the 409 has to say that rather than name a
    # holder it does not have.
    assert r2.json()["detail"]["draining"] is True
    container = _container_for(rom)
    key = session_store.session_redis_key(_key_of(container))
    ttl = asyncio.run(async_cache.ttl(key))
    # Long enough that a refresh has room to land, short enough that a backend
    # dying mid-pull does not park the container for the length of a transfer
    # nobody is doing.
    assert session_store.DRAIN_MARKER_TTL > 2 * session_store._DRAIN_MARKER_REFRESH
    assert STREAMING_SESSION_DRAIN_SECONDS < ttl <= session_store.DRAIN_MARKER_TTL


def test_save_and_exit_without_a_rom_drains_only_briefly(
    client, access_token, rom: Rom
):
    """A session with no rom (a desktop) has no exit state to collect, so
    wait=false leaves the short marker that keeps a new launch off a not-yet-dead
    emulator, not the long one that guards a pull."""
    container = _container_for(rom)
    key = session_store.session_redis_key(_key_of(container))
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        session = _load_session(key)
        session.pop("rom_id")
        asyncio.run(
            async_cache.set(key, json.dumps(session), ex=STREAMING_SESSION_TTL_SECONDS)
        )
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 10, True),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": False},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    spawn.assert_not_called()
    ttl = asyncio.run(async_cache.ttl(key))
    assert 0 < ttl <= STREAMING_SESSION_DRAIN_SECONDS


def _session_at(key: str, **fields) -> dict[str, Any]:
    """Put a session on the key and hand back the claim a route would hold."""
    session = {"user_id": 1, "claimed_at": "2026-01-01T00:00:00+00:00", **fields}
    asyncio.run(
        async_cache.set(key, json.dumps(session), ex=STREAMING_SESSION_TTL_SECONDS)
    )
    return session


def test_drain_marker_is_not_claimed_over_a_takeover():
    """Save-and-exit blocks on the broker for as long as the emulator takes to
    die, and a force-release plus a fresh claim fit in that window. The marker
    would bury a session somebody is playing."""
    key = session_store.session_redis_key("cas-takeover")
    claim = _session_at(key)
    _session_at(key, claimed_at="2026-01-01T00:05:00+00:00")
    try:
        assert (
            asyncio.run(session_store.claim_drain_marker("cas-takeover", claim)) is None
        )
        # The claim that took over is still there, untouched.
        current = _load_session(key)
        assert current["claimed_at"] == "2026-01-01T00:05:00+00:00"
        assert "draining" not in current
    finally:
        asyncio.run(async_cache.delete(key))


def test_a_stale_drain_token_frees_nobody():
    """A pull that outlived its own marker must not release whoever holds the
    container now."""
    key = session_store.session_redis_key("cas-stale-token")
    token = asyncio.run(
        session_store.claim_drain_marker("cas-stale-token", _session_at(key))
    )
    assert token is not None
    try:
        # The marker expired and a new claim took the container.
        _session_at(key, claimed_at="2026-01-01T00:05:00+00:00")
        asyncio.run(session_store.drop_drain_marker("cas-stale-token", token))
        assert asyncio.run(async_cache.get(key)) is not None
        # The drain that owns the marker still clears it.
        retaken = asyncio.run(
            session_store.claim_drain_marker(
                "cas-stale-token",
                {"user_id": 1, "claimed_at": "2026-01-01T00:05:00+00:00"},
            )
        )
        assert retaken is not None
        asyncio.run(session_store.drop_drain_marker("cas-stale-token", retaken))
        assert asyncio.run(async_cache.get(key)) is None
    finally:
        asyncio.run(async_cache.delete(key))


def test_releasing_a_session_somebody_else_holds_reports_failure():
    """The container is not this claim's to give back, and a release that says
    otherwise ends a session that had just begun."""
    key = session_store.session_redis_key("cas-release")
    claim = _session_at(key)
    _session_at(key, claimed_at="2026-01-01T00:05:00+00:00")
    try:
        assert (
            asyncio.run(session_store.release_own_session("cas-release", claim))
            is False
        )
        assert asyncio.run(async_cache.get(key)) is not None
    finally:
        asyncio.run(async_cache.delete(key))


def test_a_write_that_lands_on_nothing_is_contention_not_success():
    """A key expiring between the WATCH and the EXEC does not abort the
    transaction, so an xx write can report success having set nothing. Treating
    that as a landed marker leaves the container held by a claim the caller has
    already stopped."""

    class _NoOpPipe:
        async def watch(self, key):
            return True

        async def get(self, key):
            return json.dumps({"user_id": 1, "claimed_at": "x"})

        def multi(self):
            return None

        async def set(self, *args, **kwargs):
            return None

        async def execute(self):
            # What redis returns for a SET xx against a key that is gone.
            return [None]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    with patch.object(async_cache, "pipeline", lambda: _NoOpPipe()):
        with pytest.raises(StreamingSessionContended):
            asyncio.run(
                session_store.claim_drain_marker(
                    "cas-noop", {"user_id": 1, "claimed_at": "x"}
                )
            )


def test_a_corrupt_session_key_is_dropped_rather_than_wedging_the_container():
    """A key holding something that is not a session can never be reconciled,
    and leaving it parks the container until the TTL runs out. Both CAS paths
    drop it and report no session."""
    key = session_store.session_redis_key("cas-corrupt")
    try:
        asyncio.run(async_cache.set(key, "not a session"))
        assert (
            asyncio.run(session_store.mutate_session("cas-corrupt", {"a": 1})) is None
        )
        assert asyncio.run(async_cache.get(key)) is None

        asyncio.run(async_cache.set(key, "not a session"))
        assert (
            asyncio.run(
                session_store.replace_session_if("cas-corrupt", lambda _: True, None)
            )
            is False
        )
        assert asyncio.run(async_cache.get(key)) is None
    finally:
        asyncio.run(async_cache.delete(key))


def test_work_running_under_a_claim_keeps_it_off_the_stale_list():
    """The exit paths that could not write a drain marker run under the claim
    itself, and the player whose heartbeat kept it fresh is gone: an unrefreshed
    claim reads as abandoned and the next claimant tears the container down. The
    refresh stops at the ceiling, so a wedged step cannot hold it forever."""
    key = session_store.session_redis_key("cas-hold-claim")
    claim = _session_at(key, last_seen="2026-01-01T00:00:00+00:00")

    try:
        # A zero ceiling ends the loop on the first pass, so exactly one refresh
        # runs and the test never waits on a clock.
        with (
            patch.object(session_store, "_CLAIM_REFRESH_SECONDS", 0),
            patch.object(session_store, "HOLD_CEILING_SECONDS", 0),
        ):
            asyncio.run(session_store.hold_session_claim("cas-hold-claim", claim))
        current = _load_session(key)
        assert current["last_seen"] != "2026-01-01T00:00:00+00:00"
        assert not session_store.session_is_stale(current)
    finally:
        asyncio.run(async_cache.delete(key))


def test_holding_a_claim_stops_once_it_is_somebody_else_s():
    """Refreshing past a takeover would keep another player's session alive on
    a stamp nobody is producing."""
    key = session_store.session_redis_key("cas-hold-lost")
    claim = _session_at(key)
    _session_at(key, claimed_at="2026-01-01T00:05:00+00:00")
    try:
        with patch.object(session_store, "_CLAIM_REFRESH_SECONDS", 0):
            # Returns rather than looping forever against a claim it lost.
            asyncio.run(
                asyncio.wait_for(
                    session_store.hold_session_claim("cas-hold-lost", claim), 5
                )
            )
        current = _load_session(key)
        assert current["claimed_at"] == "2026-01-01T00:05:00+00:00"
        assert "last_seen" not in current
    finally:
        asyncio.run(async_cache.delete(key))


def test_pull_state_to_library_stores_state(rom: Rom, admin_user: User):
    """A pulled state file lands in the user's state library under the
    container's emulator namespace, keyed by the broker-supplied filename."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.03.p2s", b"state-bytes"),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 3)
        )
    assert ok is True
    wf.assert_awaited_once()
    # The library keeps every capture, so the stored name carries a stamp ahead of
    # the slot token; the container-side name is recovered by dropping it.
    stored_name = wf.await_args_list[0].kwargs["filename"]
    assert re.fullmatch(r"Game\.\d{8}-\d{12}\.03\.p2s", stored_name)
    assert states.container_state_filename(stored_name) == "Game.03.p2s"
    db_state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert db_state is not None
    assert db_state.emulator == "pcsx2"


def test_pull_state_takes_the_broker_screenshot(rom: Rom, admin_user: User):
    """Dolphin states embed no frame, so the pull takes the broker's capture."""
    container = {**_container_for(rom), "label": "Dolphin"}
    scanned = _state_for(rom, admin_user, "Game.s03", "dolphin")
    scanned_shot = _screenshot_for(rom, "Game.s03")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.s03", b"state-bytes"),
        ),
        patch(
            "handler.streaming.states.fetch_state_screenshot", return_value=_PNG
        ) as fetch_shot,
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
        patch(
            "handler.asset_store.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ) as scan_shot,
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 3)
        )
    assert ok is True
    fetch_shot.assert_called_once()
    scan_shot.assert_awaited_once()
    db_state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.s03"
    )
    assert db_state is not None
    assert db_state.screenshot is not None


def test_pull_state_prefers_broker_screenshot_over_embedded(rom: Rom, admin_user: User):
    """The container's capture is the frame the player saw, so it beats the one
    PCSX2 embedded in the state."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _state_for(rom, admin_user, "Game.05.p2s", "pcsx2")
    scanned_shot = _screenshot_for(rom, "Game.05")
    embedded = states.PNG_MAGIC + b"embedded-frame"
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.05.p2s", _p2s_bytes(embedded)),
        ),
        patch(
            "handler.streaming.states.fetch_state_screenshot", return_value=_PNG
        ) as fetch_shot,
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
        patch(
            "handler.asset_store.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 5)
        )
    assert ok is True
    fetch_shot.assert_called_once()
    assert _written_screenshot(wf) == _PNG


def test_pull_state_falls_back_to_embedded_screenshot(rom: Rom, admin_user: User):
    """A container that captured no frame leaves PCSX2's embedded one."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _state_for(rom, admin_user, "Game.06.p2s", "pcsx2")
    scanned_shot = _screenshot_for(rom, "Game.06")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.06.p2s", _p2s_bytes(_PNG)),
        ),
        patch(
            "handler.streaming.states.fetch_state_screenshot", return_value=None
        ) as fetch_shot,
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
        patch(
            "handler.asset_store.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 6)
        )
    assert ok is True
    fetch_shot.assert_called_once()
    assert _written_screenshot(wf) == _PNG


def test_pull_state_asks_the_broker_for_a_screenshot_once(rom: Rom, admin_user: User):
    """No frame from either source: the state still syncs, on one broker call."""
    container = {**_container_for(rom), "label": "RetroArch"}
    scanned = _state_for(rom, admin_user, "Game.state5", "retroarch")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.state5", b"state-bytes"),
        ),
        patch(
            "handler.streaming.states.fetch_state_screenshot", return_value=None
        ) as fetch_shot,
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
        patch("handler.asset_store.scan_screenshot", new=AsyncMock()) as scan_shot,
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 5)
        )
    assert ok is True
    fetch_shot.assert_called_once()
    scan_shot.assert_not_awaited()


def test_pull_state_rejects_unsanitizable_filename(rom: Rom, admin_user: User):
    """A broker filename that sanitizes to nothing must be dropped, not stored."""
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("***", b"bytes"),
        ),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            states.pull_state_to_library(
                admin_user.id, rom.id, _resolved(_container_for(rom)), 1
            )
        )
    assert ok is False
    wf.assert_not_awaited()


def test_pull_state_rejects_a_name_too_long_once_stamped(rom: Rom, admin_user: User):
    """A 237-byte name fits on its own, but not with the 22-byte capture stamp."""
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("a" * 230 + ".03.p2s", b"bytes"),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 3)
        )
    assert ok is False
    wf.assert_not_awaited()


def test_hydrate_pushes_only_matching_emulator_states(rom: Rom, admin_user: User):
    """Hydration must push only states saved under this container's emulator
    namespace - EmulatorJS states for the same ROM stay out of the container."""
    _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    _add_state(rom, admin_user, "Game.state", "retroarch")
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.hydrate_states_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert pushed == 1
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.01.p2s"


def test_hydrate_skips_states_missing_on_disk(rom: Rom, admin_user: User):
    """A DB row whose file vanished from disk is skipped, not fatal."""
    _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.hydrate_states_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert pushed == 0
    push.assert_not_called()


def _hydrate_core(rom: Rom, user: User, value, state_core):
    """Hydrate a RetroArch container serving the ROM as `value`, returning the
    push mock."""
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        asyncio.run(
            states.hydrate_states_to_broker(
                user.id, rom.id, _snes(value), state_core=state_core
            )
        )
    return push


def test_hydrate_pushes_an_unrecorded_state_into_the_default_core(
    rom: Rom, admin_user: User
):
    """Every state stored before cores were recorded is NULL and was written by
    the default, so an upgrade must keep hydrating it."""
    _core_state(rom, admin_user, "Game.state", None)
    push = _hydrate_core(rom, admin_user, "retroarch", states.StateCore("snes9x", True))
    push.assert_called_once()
    assert push.call_args.args[1:] == ("Game.state", b"state-bytes", "snes9x")


def test_hydrate_skips_a_newer_state_from_another_core(rom: Rom, admin_user: User):
    """The newest matching state, not the newest overall."""
    _core_state(rom, admin_user, "Old.state", "bsnes")
    _core_state(rom, admin_user, "New.state", None)
    push = _hydrate_core(
        rom, admin_user, "retroarch:bsnes", states.StateCore("bsnes", False)
    )
    assert push.call_args.args[1:] == ("Old.state", b"state-bytes", "bsnes")


def test_hydrate_pushes_a_newer_auto_state(rom: Rom, admin_user: User):
    """The broker files any pushed state into its working slot, so the auto
    state resumes like the rest."""
    _core_state(rom, admin_user, "Game.20260101-000000000000.state", None)
    _core_state(rom, admin_user, "Game.20260202-000000000000.state.auto", None)
    push = _hydrate_core(rom, admin_user, "retroarch", states.StateCore("snes9x", True))
    push.assert_called_once()
    assert push.call_args.args[1] == "Game.state.auto"


def test_hydrate_skips_a_newer_state_flagged_missing(rom: Rom, admin_user: User):
    """A row sync flagged as gone from disk can't hydrate, so the newest one
    still there goes instead of nothing."""
    _core_state(rom, admin_user, "Old.20260101-000000000000.state", None)
    _add_state(
        rom,
        admin_user,
        "New.20260202-000000000000.state",
        "retroarch",
        missing_from_fs=True,
    )
    push = _hydrate_core(rom, admin_user, "retroarch", states.StateCore("snes9x", True))
    push.assert_called_once()
    assert push.call_args.args[1] == "Old.state"


def test_hydrate_pushes_nothing_when_no_state_matches(rom: Rom, admin_user: User):
    _core_state(rom, admin_user, "Game.state", None)
    push = _hydrate_core(
        rom, admin_user, "retroarch:bsnes", states.StateCore("bsnes", False)
    )
    push.assert_not_called()


def test_hydrate_pushes_an_unrecorded_state_when_the_core_is_unknown(
    rom: Rom, admin_user: User
):
    """No configured core and a broker that can't name its default is how every
    RetroArch launch ran before cores were recorded."""
    _core_state(rom, admin_user, "Game.state", None)
    push = _hydrate_core(rom, admin_user, "retroarch", None)
    assert push.call_args.args[1:] == ("Game.state", b"state-bytes", None)


def test_hydrate_pushes_nothing_recorded_when_the_core_is_unknown(
    rom: Rom, admin_user: User
):
    """A broker too old to name its core doesn't refuse another core's state
    either, so a newest state with a recorded core stays home."""
    _core_state(rom, admin_user, "Old.state", None)
    _core_state(rom, admin_user, "New.state", "bsnes")
    push = _hydrate_core(rom, admin_user, "retroarch", None)
    push.assert_not_called()


def test_hydrate_pushes_nothing_into_a_configured_core_it_cannot_match(
    rom: Rom, admin_user: User
):
    """No filter with a core configured means the launch never said what runs,
    so nothing goes rather than something that may be the wrong core's."""
    _core_state(rom, admin_user, "Game.state", "bsnes")
    push = _hydrate_core(rom, admin_user, "retroarch:bsnes", None)
    push.assert_not_called()


def test_the_launch_hands_hydration_the_core_activate_booted(
    client, access_token, rom: Rom
):
    with patch(
        "handler.streaming.states.hydrate_states_to_broker",
        new=AsyncMock(return_value=0),
    ) as hydrate:
        _ra_claim(client, access_token, rom, "retroarch:bsnes", _BSNES_REPLY)
    assert hydrate.call_args.kwargs["state_core"] == states.StateCore("bsnes", False)


def _push_resume(rom: Rom, user: User, recorded, state_core):
    """Push a resume state recorded as written by `recorded`, returning
    (pushed, push mock)."""
    state = _core_state(rom, user, "Game.state", recorded)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.push_resume_state(_snes("retroarch:bsnes"), state, state_core)
        )
    return pushed, push


@pytest.mark.parametrize(
    ("recorded", "state_core", "label"),
    [
        ("bsnes", states.StateCore("bsnes", False), "bsnes"),
        (None, states.StateCore("snes9x", True), "snes9x"),
        # The broker's check is the backstop when RomM can't tell the core.
        ("bsnes", None, "bsnes"),
        (None, None, None),
    ],
)
def test_a_resume_push_names_the_core_that_wrote_the_state(
    rom: Rom, admin_user: User, recorded, state_core, label
):
    pushed, push = _push_resume(rom, admin_user, recorded, state_core)
    assert pushed is True
    assert push.call_args.args[3] == label


@pytest.mark.parametrize("recorded", ["snes9x", None])
def test_a_resume_push_skips_a_state_the_booted_core_cannot_load(
    rom: Rom, admin_user: User, recorded
):
    """The claim's check can disagree with the core activate booted, and the
    session then starts fresh rather than quick-loading the wrong core's file."""
    pushed, push = _push_resume(
        rom, admin_user, recorded, states.StateCore("bsnes", False)
    )
    assert pushed is False
    push.assert_not_called()


def test_resume_refuses_a_state_another_core_wrote(rom: Rom, admin_user: User):
    """A picker opened before the config change still lists it, and the claim
    is the last place to stop it."""
    state = _core_state(rom, admin_user, "Game.state", "snes9x")
    with patch("handler.streaming.webstation.default_core", return_value="snes9x"):
        with pytest.raises(HTTPException) as err:
            states.resolve_resume_state(
                admin_user.id, rom, _snes("retroarch:bsnes"), state.id
            )
    assert err.value.status_code == 400
    assert "different RetroArch core" in err.value.detail


def test_resume_takes_a_state_its_core_wrote(rom: Rom, admin_user: User):
    state = _core_state(rom, admin_user, "Game.state3", "bsnes")
    with patch("handler.streaming.webstation.default_core", return_value="snes9x"):
        picked, slot, foreign = states.resolve_resume_state(
            admin_user.id, rom, _snes("retroarch:bsnes"), state.id
        )
    assert (picked.id, slot, foreign) == (state.id, 3, False)


def test_resume_takes_an_unrecorded_state_on_the_default_core(
    rom: Rom, admin_user: User
):
    state = _core_state(rom, admin_user, "Game.state", None)
    with patch("handler.streaming.webstation.default_core", return_value="snes9x"):
        _, slot, _ = states.resolve_resume_state(
            admin_user.id, rom, _snes("retroarch"), state.id
        )
    assert slot == 0


# ── A RetroArch stream shares each core's states with every other client ──────


def test_a_streamed_state_is_the_one_cloud_sync_serves_for_its_slot(
    rom: Rom, admin_user: User
):
    _add_state(rom, admin_user, "Game.state.auto", "mgba")
    streamed = _add_state(
        rom,
        admin_user,
        "Game.20261008-153825000000.state.auto",
        "mgba",
        core="mgba",
        updated_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )

    served = retroarch_sync.resolve_state_by_slot(
        admin_user, rom, "mgba", "Game.state.auto"
    )
    assert served is not None and served.id == streamed.id


def test_a_retroarch_core_loads_its_own_states_from_every_client(
    rom: Rom, admin_user: User
):
    synced = _add_state(rom, admin_user, "Game.state1", "mgba")
    streamed = _add_state(rom, admin_user, "Game.state", "mgba", core="mgba")
    legacy = _core_state(rom, admin_user, "Old.state", "mgba")
    _core_state(rom, admin_user, "Other.state", "vba_next")
    _add_state(rom, admin_user, "Other.state1", "vba_next")

    loadable = states.user_states_for_emulator(
        admin_user.id, rom.id, "retroarch", states.StateCore("mgba", True)
    )

    assert {s.id for s in loadable} == {synced.id, streamed.id, legacy.id}


def test_a_retroarch_core_loads_states_filed_under_an_alias_of_its_folder(
    rom: Rom, admin_user: User
):
    """Cloud Sync slots beetle_psx_hw with mednafen_psx_hw, both "Beetle PSX HW"."""
    aliased = _add_state(rom, admin_user, "Game.state1", "beetle_psx_hw")
    _add_state(rom, admin_user, "Other.state1", "mednafen_psx")

    loadable = states.user_states_for_emulator(
        admin_user.id,
        rom.id,
        "retroarch",
        states.StateCore("mednafen_psx_hw", True, folder="mednafen_psx_hw"),
    )

    assert [s.id for s in loadable] == [aliased.id]


def test_a_stream_never_prunes_another_clients_state(rom: Rom, admin_user: User):
    """The stream's retention covers what it filed; Cloud Sync's and the
    device clients' states under the same core are theirs to keep."""
    synced = _add_state(
        rom,
        admin_user,
        "Game.state1",
        "mgba",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    legacy = _core_state(rom, admin_user, "Game.20260102-000000000000.state", "mgba")
    db_state_handler.update_state(
        legacy.id, {"updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc)}
    )
    _core_state(rom, admin_user, "Game.20260103-000000000000.state", "mgba")

    remaining = _prune_to_one(rom, admin_user)

    assert synced.id in remaining
    assert legacy.id not in remaining


@pytest.mark.parametrize(
    ("folder", "core", "library_name"),
    [("bsnes", "bsnes", None), ("Snes9x 2010", "snes9x2010", "Snes9x 2010")],
)
def test_resume_takes_a_cloud_synced_state_of_the_booted_core(
    rom: Rom, admin_user: User, folder, core, library_name
):
    """Filed under the core's folder, or its id when the broker names none, the
    state is this container's own and resumes without an import."""
    state = _add_state(rom, admin_user, "Game.state2", folder)
    reply = {
        "platform": "snes",
        "default": "snes9x",
        "cores": [{"core": core, "library_name": library_name}],
    }
    with patch("handler.streaming.broker.request", return_value=reply):
        picked, slot, foreign = states.resolve_resume_state(
            admin_user.id, rom, _snes(f"retroarch:{core}"), state.id
        )
    assert (picked.id, slot, foreign) == (state.id, 2, False)


@pytest.mark.parametrize(
    ("folder", "core"),
    [
        ("bsnes", states.StateCore("bsnes", False)),
        ("Snes9x 2010", states.StateCore("snes9x2010", False, folder="Snes9x 2010")),
    ],
)
def test_a_resume_push_sends_a_cloud_synced_state_of_the_booted_core(
    rom: Rom, admin_user: User, folder: str, core: states.StateCore
):
    """The claim took it as the core's own, so the push must not refuse it."""
    state = _add_state(rom, admin_user, "Game.state2", folder)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.push_resume_state(_snes(f"retroarch:{core.expected}"), state, core)
        )
    assert pushed is True
    assert push.call_args.args[3] == core.expected


@pytest.mark.parametrize("folder", ["bsnes", "Snes9x 2010"])
def test_resume_takes_the_streams_own_state_when_the_core_is_unknown(
    rom: Rom, admin_user: User, folder: str
):
    """Filed under the core's folder with the core it recorded, it is still the
    stream's own; the broker refuses it if another core booted."""
    state = _add_state(rom, admin_user, "Game.state3", folder, core="bsnes")
    with patch("handler.streaming.webstation.default_core", return_value=None):
        picked, slot, foreign = states.resolve_resume_state(
            admin_user.id, rom, _snes("retroarch"), state.id
        )
    assert (picked.id, slot, foreign) == (state.id, 3, False)


def test_hydrate_pushes_a_newer_cloud_synced_state_of_the_booted_core(
    rom: Rom, admin_user: User
):
    _core_state(rom, admin_user, "Old.20260101-000000000000.state", "bsnes")
    _add_state(
        rom,
        admin_user,
        "Game.state.auto",
        "bsnes",
        updated_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    push = _hydrate_core(
        rom, admin_user, "retroarch:bsnes", states.StateCore("bsnes", False)
    )
    assert push.call_args.args[1:] == ("Game.state.auto", b"state-bytes", "bsnes")


# ── A RetroArch stream files under the folder RetroArch names the core's ──────


@pytest.mark.parametrize(
    ("core", "library_name", "folder"),
    [
        # Cloud Sync files RetroArch's "mGBA" folder under the web player's id.
        ("mgba", "mGBA", "mgba"),
        ("melondsds", "melonDS DS", "melonDS DS"),
        # A broker too old to name the folder leaves the core id.
        ("melondsds", None, "melondsds"),
        ("melondsds", "", "melondsds"),
        ("melondsds", "bad/name", "melondsds"),
        ("melondsds", "x" * 300, "melondsds"),
        ("bad/core", None, "retroarch"),
        (None, None, "retroarch"),
        # With no core to mark it a capture, the folder would pass it off as
        # another client's state.
        (None, "melonDS DS", "retroarch"),
    ],
)
def test_a_retroarch_state_is_filed_under_the_cores_folder(core, library_name, folder):
    assert states.filed_emulator("retroarch", core, library_name) == folder


def test_other_emulators_file_under_the_emulator():
    assert states.filed_emulator("pcsx2", "mgba", "mGBA") == "pcsx2"


@pytest.mark.parametrize(
    ("core", "library_name", "folder"),
    [("mgba", None, "mgba"), ("melondsds", "melonDS DS", "melonDS DS")],
)
def test_a_streamed_state_is_filed_where_cloud_sync_files_its_core(
    rom: Rom, admin_user: User, core, library_name, folder
):
    """Clients file states under the core's folder, named after RetroArch's
    library name, which for melonDS DS is not its core id."""

    async def scanned(**kwargs: Any) -> State:
        return _state_for(rom, admin_user, kwargs["file_name"], kwargs["emulator"])

    with (
        patch("handler.asset_store.scan_state", new=AsyncMock(side_effect=scanned)),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
    ):
        asyncio.run(
            states.store_state_asset(
                admin_user,
                rom,
                "retroarch",
                "Game.state",
                b"s",
                core=core,
                library_name=library_name,
            )
        )

    [stored] = db_state_handler.get_states(user_id=admin_user.id, rom_ids=[rom.id])
    assert (stored.emulator, stored.core) == (folder, core)
    assert re.fullmatch(r"Game\.\d{8}-\d{12}\.state", stored.file_name)


def test_a_core_loads_every_clients_states_in_its_folder(rom: Rom, admin_user: User):
    synced = _add_state(rom, admin_user, "Game.state1", "melonDS DS")
    streamed = _add_state(rom, admin_user, "Game.state", "melonDS DS", core="melondsds")
    # Filed under the core id while the broker could not name the folder.
    unnamed = _add_state(rom, admin_user, "Game.state2", "melondsds", core="melondsds")
    _add_state(rom, admin_user, "Other.state", "melonDS DS", core="melonds")
    _add_state(rom, admin_user, "Other.state1", "melonDS")

    loadable = states.user_states_for_emulator(
        admin_user.id,
        rom.id,
        "retroarch",
        states.StateCore("melondsds", True, folder="melonDS DS"),
    )

    assert {s.id for s in loadable} == {synced.id, streamed.id, unnamed.id}


def test_a_stream_keeps_its_history_across_folders(rom: Rom, admin_user: User):
    """Prune and dedup cover every state a stream filed, whichever folder."""
    streamed = _add_state(rom, admin_user, "Game.state", "melonDS DS", core="melondsds")
    unnamed = _add_state(rom, admin_user, "Game.state2", "melondsds", core="melondsds")
    _add_state(rom, admin_user, "Game.state1", "melonDS DS")

    history = states.user_states_for_emulator(admin_user.id, rom.id, "retroarch")

    assert {s.id for s in history} == {streamed.id, unnamed.id}


def _add_state_at(rom: Rom, user: User, file_name: str, day: int) -> State:
    """Add a state with an explicit updated_at, so history order is deterministic."""
    stored = _add_state(rom, user, file_name, "pcsx2")
    db_state_handler.update_state(
        stored.id, {"updated_at": datetime(2026, 1, day, tzinfo=timezone.utc)}
    )
    return stored


def test_hydrate_skipped_when_resume_state_already_pushed(rom: Rom, admin_user: User):
    """Every history entry collapses to the same container-side name, so pushing
    anything here would overwrite the state the player picked to resume from."""
    _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    container = {**_container_for(rom), "label": "PCSX2"}
    with patch("handler.streaming.states.push_state_file", return_value=True) as push:
        pushed = asyncio.run(
            states.hydrate_states_to_broker(
                admin_user.id, rom.id, _resolved(container), resume_pushed=True
            )
        )
    assert pushed == 0
    push.assert_not_called()


@pytest.mark.parametrize(
    ("emulator", "name"),
    [
        ("duckstation", "SLUS-00594_resume.20260918-010000000000.sav"),
        ("rpcs3", "BLUS30443_1.20260918-010000000000.SAVESTAT"),
    ],
)
def test_hydrate_pushes_nothing_to_an_exit_state_emulator(
    rom: Rom, admin_user: User, emulator, name
):
    """Their broker refuses a state file, and the save archive already carries
    the exit state these library entries were pulled from."""
    _add_state(rom, admin_user, name, emulator)
    container = {**_container_for(rom), "protocol": "webstation", "emulator": emulator}
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.hydrate_states_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert pushed == 0
    push.assert_not_called()


def test_hydrate_pushes_newest_state_under_container_name(rom: Rom, admin_user: User):
    """Only the newest capture is hydrated, and it lands under the unstamped name
    the emulator expects on disk."""
    _add_state_at(rom, admin_user, "Game.20260101-000000000000.01.p2s", 1)
    newest = _add_state_at(rom, admin_user, "Game.20260202-000000000000.01.p2s", 2)
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        # Both stamps collapse to the same destination name, so only the bytes
        # say which source was read; a constant here would pass either way.
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=lambda path: path.encode()),
        ),
        patch("handler.streaming.states.push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            states.hydrate_states_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert pushed == 1
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.01.p2s"
    assert push.call_args[0][2] == newest.full_path.encode()


def test_pull_state_skips_capture_identical_to_previous(rom: Rom, admin_user: User):
    """Saving twice without playing in between produces the same bytes, and the
    duplicate must not take a history slot."""
    content = b"state-bytes"
    _add_state(
        rom,
        admin_user,
        "Game.20260101-000000000000.03.p2s",
        "pcsx2",
        file_size_bytes=len(content),
    )
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.03.p2s", content),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=content),
        ),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 3)
        )
    assert ok is True
    wf.assert_not_awaited()


def test_a_hashed_state_is_matched_without_reading_its_file(rom: Rom, admin_user: User):
    content = b"state-bytes"
    _add_state(
        rom,
        admin_user,
        "Game.state",
        "retroarch",
        file_size_bytes=len(content),
        content_hash=content_hash_of_bytes(content),
    )
    read = AsyncMock(side_effect=AssertionError("read a hashed state"))
    with (
        patch("handler.filesystem.fs_asset_handler.read_file", new=read),
        patch(
            "handler.filesystem.fs_asset_handler.file_exists",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", content)
        )
        assert not asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", b"other-bytes")
        )
    read.assert_not_awaited()


def test_a_hashed_state_whose_file_is_gone_is_not_a_match(rom: Rom, admin_user: User):
    """The capture is the only copy left, so it must not be skipped."""
    content = b"state-bytes"
    _add_state(
        rom,
        admin_user,
        "Game.state",
        "retroarch",
        file_size_bytes=len(content),
        content_hash=content_hash_of_bytes(content),
    )
    with patch(
        "handler.filesystem.fs_asset_handler.file_exists",
        new=AsyncMock(return_value=False),
    ):
        assert not asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", content)
        )


def test_an_unhashed_state_is_still_matched_by_its_bytes(rom: Rom, admin_user: User):
    """A state stored before states were hashed has no hash to compare."""
    content = b"state-bytes"
    _add_state(rom, admin_user, "Game.state", "retroarch", file_size_bytes=len(content))
    with patch(
        "handler.filesystem.fs_asset_handler.read_file",
        new=AsyncMock(return_value=content),
    ):
        assert asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", content)
        )


def test_an_unhashed_state_gets_its_hash_once_read(rom: Rom, admin_user: User):
    """The next dedupe check then compares hashes rather than reading the file."""
    content = b"state-bytes"
    state = _add_state(
        rom, admin_user, "Game.state", "retroarch", file_size_bytes=len(content)
    )
    before = db_state_handler.get_state_by_id(state.id)
    assert before is not None
    with patch(
        "handler.filesystem.fs_asset_handler.read_file",
        new=AsyncMock(return_value=content),
    ):
        asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", b"other-bytes")
        )
    row = db_state_handler.get_state(user_id=admin_user.id, id=state.id)
    assert row is not None
    assert row.content_hash == content_hash_of_bytes(content)
    assert row.updated_at == before.updated_at


def test_a_failed_hash_write_back_still_matches_the_state(
    rom: Rom, admin_user: User, caplog
):
    content = b"state-bytes"
    _add_state(rom, admin_user, "Game.state", "retroarch", file_size_bytes=len(content))
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=content),
        ),
        patch(
            "handler.streaming.states.db_state_handler.backfill_content_hash",
            side_effect=RuntimeError("db down"),
        ),
    ):
        assert asyncio.run(
            states.stored_copy(admin_user.id, rom.id, "retroarch", content)
        )
    assert "db down" in caplog.text


def test_a_stored_state_records_its_content_hash(rom: Rom, admin_user: User):
    content = b"state-bytes"
    with (
        patch(
            "handler.filesystem.fs_asset_handler.compute_content_hash",
            new=AsyncMock(return_value=content_hash_of_bytes(content)),
        ),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "handler.scan_handler.fs_asset_handler.get_file_size",
            return_value=len(content),
        ),
    ):
        stored = asyncio.run(
            asset_store.store_state_file(
                admin_user, rom, "retroarch", content, "Game.state"
            )
        )
    assert stored.content_hash == content_hash_of_bytes(content)


def test_prune_state_history_drops_oldest_past_limit(rom: Rom, admin_user: User):
    """Once the retention limit is reached the oldest captures go, newest first
    order preserved."""
    for day in range(1, 4):
        _add_state_at(rom, admin_user, f"Game.2026010{day}-000000000000.01.p2s", day)
    with (
        patch("handler.streaming.states.STREAMING_STATE_HISTORY_LIMIT", 2),
        patch(
            "handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()
        ) as remove,
    ):
        pruned = asyncio.run(states.prune_state_history(admin_user, rom, "pcsx2"))
    assert pruned == 1
    remove.assert_awaited_once()
    remaining = {
        s.file_name
        for s in db_state_handler.get_states(user_id=admin_user.id, rom_ids=[rom.id])
    }
    assert remaining == {
        "Game.20260102-000000000000.01.p2s",
        "Game.20260103-000000000000.01.p2s",
    }


def _prune_to_one(rom: Rom, user: User) -> set[int]:
    with (
        patch("handler.streaming.states.STREAMING_STATE_HISTORY_LIMIT", 1),
        patch("handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()),
    ):
        asyncio.run(states.prune_state_history(user, rom, "retroarch"))
    return {
        s.id for s in db_state_handler.get_states(user_id=user.id, rom_ids=[rom.id])
    }


def test_prune_state_history_drops_the_pruned_thumbnail(rom: Rom, admin_user: User):
    for day in range(1, 4):
        _add_state_at(rom, admin_user, f"Game.2026010{day}-000000000000.01.p2s", day)
    thumbnail = make_screenshot(
        rom, admin_user, "Game.20260101-000000000000.01.png", file_size_bytes=3
    )
    with (
        patch("handler.streaming.states.STREAMING_STATE_HISTORY_LIMIT", 2),
        patch(
            "handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()
        ) as remove,
    ):
        asyncio.run(states.prune_state_history(admin_user, rom, "pcsx2"))

    assert remove.await_count == 2
    assert db_screenshot_handler.get_screenshot_by_id(thumbnail.id) is None


# _store_state_screenshot rejects anything without PNG magic, so fixtures that
# reach it need real header bytes rather than a stand-in string.
_PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"


def _p2s_bytes(screenshot: bytes | None = _PNG) -> bytes:
    """Build a PCSX2 .p2s-shaped zip, optionally embedding a Screenshot.png."""
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Sstates.bin", b"savestate-payload")
        if screenshot is not None:
            zf.writestr("Screenshot.png", screenshot)
    return buf.getvalue()


def test_extract_state_screenshot_pcsx2_returns_png():
    assert states.extract_state_screenshot("pcsx2", _p2s_bytes(_PNG)) == _PNG


def test_extract_state_screenshot_non_pcsx2_returns_none():
    # Dolphin states embed no frame; its broker serves one from /state-screenshot.
    assert states.extract_state_screenshot("dolphin", _p2s_bytes()) is None


def test_extract_state_screenshot_missing_entry_returns_none():
    assert states.extract_state_screenshot("pcsx2", _p2s_bytes(None)) is None


def test_extract_state_screenshot_empty_entry_returns_none():
    assert states.extract_state_screenshot("pcsx2", _p2s_bytes(b"")) is None


def test_extract_state_screenshot_not_a_zip_returns_none():
    assert states.extract_state_screenshot("pcsx2", b"not-a-zip") is None


def test_fetch_state_screenshot_rejects_a_non_png_body(rom: Rom):
    """A body that is not a PNG has to read as no frame, or it would shadow the
    frame a state embeds for itself and leave the state with no thumbnail."""
    with patch(
        "handler.streaming.broker.get_binary_safe",
        return_value=(MagicMock(), b"GIF89a-not-a-png"),
    ):
        assert states.fetch_state_screenshot(_resolved(_container_for(rom)), 3) is None


def test_state_transfer_limits_default_for_an_unlisted_emulator():
    assert state_transfer_limits("pcsx2") == DEFAULT_STATE_TRANSFER


def test_state_transfer_limits_are_larger_for_xemu():
    """A xemu state is the whole Xbox hard disk, not a RAM snapshot."""
    default = DEFAULT_STATE_TRANSFER
    xemu = state_transfer_limits("xemu")
    assert xemu["max_bytes"] > default["max_bytes"]
    # The ceiling is useless if the body cannot finish arriving inside it.
    assert xemu["timeout"] > default["timeout"]


def test_fetch_state_file_reads_and_waits_to_the_emulator_limits(rom: Rom):
    resp = MagicMock()
    inner = resp.__enter__.return_value
    inner.read.side_effect = _reads(b"state-bytes")
    inner.headers = {"X-State-Filename": "game.xemu.state"}
    container = dict(_container_for(rom), emulator="xemu")

    with patch(
        "handler.streaming.broker.urllib.request.urlopen", return_value=resp
    ) as urlopen:
        assert states.fetch_state_file(_resolved(container), 1) == states.PulledState(
            "game.xemu.state", b"state-bytes"
        )

    limits = state_transfer_limits("xemu")
    assert urlopen.call_args.kwargs["timeout"] == limits["timeout"]
    # The read is chunked, but never asks for more in total than the ceiling it
    # will accept, plus the one byte that proves the body overran it.
    requested = sum(call.args[0] for call in inner.read.call_args_list)
    assert requested <= limits["max_bytes"] + 1


def test_push_state_file_waits_to_the_emulator_limits(rom: Rom):
    resp = MagicMock()
    resp.__enter__.return_value.read.side_effect = _reads(b'{"status": "ok"}')
    container = dict(_container_for(rom), emulator="xemu")

    with patch(
        "handler.streaming.broker.urllib.request.urlopen", return_value=resp
    ) as urlopen:
        assert states.push_state_file(_resolved(container), "game.xemu.state", b"bytes")

    assert (
        urlopen.call_args.kwargs["timeout"] == state_transfer_limits("xemu")["timeout"]
    )


def test_fetch_state_screenshot_returns_png(rom: Rom):
    resp = MagicMock()
    resp.__enter__.return_value.read.side_effect = _reads(_PNG)
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        assert states.fetch_state_screenshot(_resolved(_container_for(rom)), 1) == _PNG


def test_fetch_state_screenshot_404_returns_none(rom: Rom):
    """A broker that captures no frames answers 404; that is not an error."""
    with patch(
        "handler.streaming.broker.urllib.request.urlopen", side_effect=_http_error(404)
    ):
        assert states.fetch_state_screenshot(_resolved(_container_for(rom)), 1) is None


def test_fetch_state_screenshot_transport_error_returns_none(rom: Rom):
    import urllib.error

    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=urllib.error.URLError("broker down"),
    ):
        assert states.fetch_state_screenshot(_resolved(_container_for(rom)), 1) is None


def test_store_state_screenshot_binds_to_state(admin_user: User, rom: Rom):
    """A stored state screenshot lands in the screenshots dir under the state's
    stem, so State.screenshot resolves it as the resume-picker thumbnail."""
    _add_state(rom, admin_user, "Game.03.p2s", "pcsx2")
    scanned = _screenshot_for(rom, "Game.03")
    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch(
            "handler.asset_store.scan_screenshot",
            new=AsyncMock(return_value=scanned),
        ),
    ):
        asyncio.run(states.store_state_screenshot(admin_user, rom, "Game.03.p2s", _PNG))
    wf.assert_awaited_once()
    assert wf.await_args_list[0].kwargs["filename"] == "Game.03.png"
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert state is not None
    assert state.screenshot is not None
    assert state.screenshot.file_name == "Game.03.png"
    assert state.screenshot.is_gallery is False


def test_store_state_screenshot_rejects_non_png(admin_user: User, rom: Rom):
    """A broker error page must never be written out as a thumbnail."""
    _add_state(rom, admin_user, "Game.05.p2s", "pcsx2")
    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.asset_store.scan_screenshot", new=AsyncMock()) as scan,
    ):
        asyncio.run(
            states.store_state_screenshot(
                admin_user, rom, "Game.05.p2s", b"<html>404</html>"
            )
        )
    wf.assert_not_awaited()
    scan.assert_not_awaited()
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.05.p2s"
    )
    assert state is not None
    assert state.screenshot is None


def test_store_state_asset_binds_screenshot(admin_user: User, rom: Rom):
    """End to end: storing a state with a frame binds it as the thumbnail."""
    scanned_state = _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    scanned_shot = _screenshot_for(rom, "Game.03")
    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "handler.asset_store.scan_state",
            new=AsyncMock(return_value=scanned_state),
        ),
        patch(
            "handler.asset_store.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ) as scan_shot,
    ):
        asyncio.run(
            states.store_state_asset(
                admin_user, rom, "pcsx2", "Game.03.p2s", _p2s_bytes(_PNG), _PNG
            )
        )
    scan_shot.assert_awaited_once()
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert state is not None
    assert state.screenshot is not None
    assert state.screenshot.file_name == "Game.03.png"


def test_store_state_asset_without_screenshot_still_stores_state(
    admin_user: User, rom: Rom
):
    """A state with no frame syncs with no thumbnail; the missing screenshot
    must not fail the state sync."""
    scanned_state = _state_for(rom, admin_user, "Game.04.p2s", "pcsx2")
    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "handler.asset_store.scan_state",
            new=AsyncMock(return_value=scanned_state),
        ),
        patch("handler.asset_store.scan_screenshot", new=AsyncMock()) as scan_shot,
    ):
        asyncio.run(
            states.store_state_asset(
                admin_user, rom, "pcsx2", "Game.04.p2s", _p2s_bytes(None)
            )
        )
    scan_shot.assert_not_awaited()
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.04.p2s"
    )
    assert state is not None
    assert state.screenshot is None


def test_store_state_asset_collision_keeps_disc_file_id_in_sync(
    admin_user: User, rom: Rom
):
    """A same-second capture collides with the row already on disk instead of
    adding a new one; the update must also refresh which disc it was captured
    on, not just the file size."""
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stamped = states.stamped_state_filename("pcsx2", "Game.03.p2s", when)
    existing = _add_state(rom, admin_user, stamped, "pcsx2")
    scanned_state = _state_for(rom, admin_user, stamped, "pcsx2")
    scanned_state.file_size_bytes = 999
    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "handler.asset_store.scan_state",
            new=AsyncMock(return_value=scanned_state),
        ),
        patch("handler.streaming.states.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = when
        asyncio.run(
            states.store_state_asset(
                admin_user,
                rom,
                "pcsx2",
                "Game.03.p2s",
                _p2s_bytes(None),
                disc_file_id=disc.id,
            )
        )
    updated = db_state_handler.get_state_by_id(existing.id)
    assert updated is not None
    assert updated.disc_file_id == disc.id
    assert updated.file_size_bytes == 999


# ── In-game save sync ─────────────────────────────────────────────────────────


def _save_fields(
    rom: Rom, file_name: str, emulator: str, content_hash: str | None
) -> dict[str, Any]:
    # Unlike the model's split, a tagged archive keeps `zip` as its extension.
    name_no_ext, _, extension = file_name.rpartition(".")
    return {
        "file_name_no_tags": name_no_ext,
        "file_name_no_ext": name_no_ext,
        "file_extension": extension,
        "emulator": emulator,
        "content_hash": content_hash,
        "file_path": f"{rom.platform_slug}/saves/{emulator}",
        "file_size_bytes": 1.0,
    }


def _save_for(
    rom: Rom, user: User, file_name: str, emulator: str, content_hash: str | None = None
) -> Save:
    """An unsaved save, as a patched scan_save returns one."""
    return Save(
        rom_id=rom.id,
        user_id=user.id,
        file_name=file_name,
        **_save_fields(rom, file_name, emulator, content_hash),
    )


def _add_save(
    rom: Rom,
    user: User,
    file_name: str,
    emulator: str,
    content_hash: str | None = None,
    **overrides: Any,
) -> Save:
    return make_save(
        rom,
        user,
        file_name,
        **(_save_fields(rom, file_name, emulator, content_hash) | overrides),
    )


def test_pull_saves_stores_new_archive(rom: Rom, admin_user: User):
    """A pulled save archive lands as a new Save asset under the container's
    emulator namespace."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _save_for(rom, admin_user, "Game [pcsx2].saves.zip", "pcsx2", "hash-a")
    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=b"zip-bytes"),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.streaming.saves.scan_save", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            saves.pull_saves_to_library(admin_user.id, rom.id, _resolved(container))
        )
    assert ok is True
    wf.assert_awaited_once()
    stored = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
    assert any(s.emulator == "pcsx2" and s.content_hash == "hash-a" for s in stored)


def test_pull_saves_dedups_identical_archive(rom: Rom, admin_user: User):
    """Re-pulling an unchanged archive (same content hash) must not add a second
    row, and must delete the just-written duplicate file."""
    _add_save(rom, admin_user, "Game [pcsx2 old].saves.zip", "pcsx2", "dup-hash")
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _save_for(
        rom, admin_user, "Game [pcsx2 new].saves.zip", "pcsx2", "dup-hash"
    )
    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=b"zip-bytes"),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.streaming.saves.scan_save", new=AsyncMock(return_value=scanned)),
        patch("handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()) as rm,
    ):
        ok = asyncio.run(
            saves.pull_saves_to_library(admin_user.id, rom.id, _resolved(container))
        )
    assert ok is True
    rm.assert_awaited_once()
    stored = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
    hashes = [s.content_hash for s in stored if s.emulator == "pcsx2"]
    assert hashes == ["dup-hash"]


def test_pull_saves_no_changes_returns_false(rom: Rom, admin_user: User):
    """A 404 from the broker (nothing changed) yields no stored save."""
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=None),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            saves.pull_saves_to_library(admin_user.id, rom.id, _resolved(container))
        )
    assert ok is False
    wf.assert_not_awaited()


# ── A RetroArch exit filed as raw files ───────────────────────────────────────


_SAVE_IMPORT = webstation.ImportSpec(
    kinds=frozenset({"save"}), state_channel="push", state_slot=None
)


def _exit_archive(
    members: dict[str, tuple[Any, bytes]],
    core: str | None = "mgba",
    written: dict[str, tuple[int, int, int, int, int, int]] | None = None,
    library_name: object = None,
) -> bytes:
    """A webstation exit archive whose manifest labels each member with its kind,
    each member stamped with its `written` time when one is given."""
    ensure_zipfile_writable()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, (_kind, content) in members.items():
            stamp = (written or {}).get(path)
            zf.writestr(
                zipfile.ZipInfo(path, date_time=stamp) if stamp else path, content
            )
        session: dict[str, Any] = {"emulator": "retroarch", "platform": "gba"}
        if core is not None:
            session["core"] = core
        if library_name is not None:
            session["library_name"] = library_name
        zf.writestr(
            ".broker-manifest.json",
            json.dumps(
                {
                    "version": 1,
                    "session": session,
                    "files": [
                        {"path": path, "kind": kind}
                        for path, (kind, _content) in members.items()
                    ],
                }
            ),
        )
    return buf.getvalue()


def _pull_exit(
    rom: Rom,
    user: User,
    content: bytes,
    emulator: str = "retroarch",
    spec: webstation.ImportSpec | None = _SAVE_IMPORT,
    disc_file_id: int | None = None,
    store_state: AsyncMock | None = None,
    disc_swaps: list[session_store.DiscSwap] | None = None,
) -> tuple[MagicMock, AsyncMock]:
    """Run an exit pull of `content` against a broker declaring `spec`,
    returning the file write and state store mocks."""
    container = {**_clearing_webstation(rom), "emulator": emulator}

    async def scanned(**kwargs: Any) -> Save:
        name = kwargs["file_name"]
        return _save_for(rom, user, name, kwargs["emulator"], f"h{len(name)}")

    store_state = store_state or AsyncMock()
    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=content),
        patch("handler.streaming.saves.webstation.import_spec", return_value=spec),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("handler.streaming.saves.scan_save", new=AsyncMock(side_effect=scanned)),
        patch("handler.streaming.saves.states.store_state_asset", store_state),
    ):
        assert asyncio.run(
            saves.pull_saves_to_library(
                user.id,
                rom.id,
                _resolved(container),
                disc_file_id=disc_file_id,
                disc_swaps=disc_swaps or [],
            )
        )
    return wf, store_state


def _stored_saves(rom: Rom, user: User) -> list[Save]:
    return list(db_save_handler.get_saves(user_id=user.id, rom_ids=[rom.id]))


@pytest.mark.parametrize(
    ("core", "library_name", "folder", "recorded"),
    [
        ("melondsds", "melonDS DS", "melonDS DS", "melonDS DS"),
        ("mgba", "mGBA", "mgba", "mGBA"),
        ("melondsds", None, "melondsds", None),
        ("melondsds", "bad/name", "melondsds", "bad/name"),
        # Not a string, so not a name at all.
        ("melondsds", 7, "melondsds", None),
    ],
)
def test_a_retroarch_exit_files_under_the_cores_folder(
    rom: Rom, admin_user: User, core, library_name, folder, recorded
):
    """Where RetroArch, and so Cloud Sync, files that core's saves and states."""
    content = _exit_archive(
        {
            "saves/x/Game.srm": ("save", b"sram"),
            "states/x/Game.state": ("state", b"state-bytes"),
        },
        core=core,
        library_name=library_name,
    )
    _write, store_state = _pull_exit(rom, admin_user, content)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.emulator == folder
    kwargs = store_state.call_args.kwargs
    assert (kwargs["core"], kwargs["library_name"]) == (core, recorded)


def test_a_retroarch_exit_files_its_one_save_raw_and_its_state_apart(
    rom: Rom, admin_user: User
):
    """The save lands as the bare .srm under the core, the way the web player
    and Cloud Sync store one, and no zip is kept."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"state-bytes"),
            "states/mGBA/Game.state.png": ("state_screenshot", b"png-bytes"),
        }
    )
    write, store_state = _pull_exit(rom, admin_user, content)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.emulator == "mgba"
    assert stored.slot == AUTOSAVE_SLOT
    assert re.fullmatch(
        re.escape(rom.fs_name_no_ext)
        + r" \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\]\.srm",
        stored.file_name,
    )
    write.assert_awaited_once()
    assert write.call_args.kwargs["file"] == b"eeprom"
    store_state.assert_awaited_once()
    args = store_state.call_args
    assert args.args[2:5] == ("retroarch", "Game.state", b"state-bytes")
    assert args.kwargs["screenshot"] == b"png-bytes"
    assert args.kwargs["core"] == "mgba"


def test_a_raw_exit_save_is_the_version_retroarch_cloud_sync_serves(
    rom: Rom, admin_user: User
):
    """Cloud Sync and the device clients read the core's `autosave` head."""
    older = _add_save(
        rom, admin_user, "Game [older].srm", "mgba", "old", slot=AUTOSAVE_SLOT
    )
    _stamp(
        older,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})

    _pull_exit(rom, admin_user, content)

    served = retroarch_sync.resolve_save(
        admin_user, rom, "mgba", f"{rom.fs_name_no_ext}.srm"
    )
    assert served is not None
    assert served.id != older.id
    assert served.slot == AUTOSAVE_SLOT


def test_a_raw_exit_save_matching_only_an_unslotted_save_still_files(
    rom: Rom, admin_user: User
):
    """An exit filed before saves went through the slot is invisible to Cloud
    Sync, so the same bytes are filed again where it reads them."""
    _add_save(rom, admin_user, "Game [old].srm", "mgba", "same")

    rm = _pull_raw_exit_save(rom, admin_user, "same")

    rm.assert_not_awaited()
    slotted = [s for s in _stored_saves(rom, admin_user) if s.slot == AUTOSAVE_SLOT]
    assert len(slotted) == 1


def test_a_raw_exit_save_prunes_only_its_own_cores_autosave_versions(
    rom: Rom, admin_user: User
):
    for day, name in ((1, "Game [a].srm"), (2, "Game [b].srm")):
        version = _add_save(
            rom, admin_user, name, "mgba", f"h-{name}", slot=AUTOSAVE_SLOT
        )
        when = datetime(2026, 10, day, tzinfo=timezone.utc)
        _stamp(version, when, when)
    other_core = _add_save(
        rom, admin_user, "Game [c].srm", "vba_next", "h-c", slot=AUTOSAVE_SLOT
    )
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})

    with (
        patch("handler.sync.retroarch.sync_handler.MAX_SAVES_PER_SLOT", 2),
        patch("handler.asset_store.remove_asset_file", new=AsyncMock()),
    ):
        _pull_exit(rom, admin_user, content)

    names = {s.file_name for s in _stored_saves(rom, admin_user)}
    assert "Game [a].srm" not in names
    assert "Game [b].srm" in names
    assert other_core.file_name in names
    assert len(names) == 3


def test_a_raw_exit_save_skips_a_version_name_already_taken(rom: Rom, admin_user: User):
    now = datetime(2026, 10, 7, 12, 0, 0)
    taken = asset_store.apply_datetime_tag(f"{rom.fs_name_no_ext}.srm", now)
    saves_path = fs_asset_handler.build_saves_file_path(
        user=admin_user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator="mgba",
    )
    make_save(
        rom,
        admin_user,
        taken,
        **{**_save_fields(rom, taken, "mgba", "older"), "file_path": saves_path},
    )
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})

    with patch("handler.asset_store.datetime", wraps=datetime) as clock:
        clock.now.return_value = now
        write, _store_state = _pull_exit(rom, admin_user, content)

    written = write.call_args.kwargs["filename"]
    assert written == asset_store.apply_datetime_tag(
        f"{rom.fs_name_no_ext}.srm", now + timedelta(seconds=1)
    )


def test_a_retroarch_exit_files_its_states_on_the_swapped_disc(
    rom: Rom, admin_user: User
):
    """The background pull files the exit's states too, so it must bind them to
    the disc the session swapped to, as the exit-state pull does."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"state-bytes"),
        }
    )
    _write, store_state = _pull_exit(rom, admin_user, content, disc_file_id=42)

    assert store_state.call_args.kwargs["disc_file_id"] == 42


def test_a_retroarch_exit_files_each_state_on_the_disc_it_was_saved_on(
    rom: Rom, admin_user: User
):
    """A hotkey slot only reaches RomM in the exit archive, after later swaps."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state1": ("state", b"before"),
            "states/mGBA/Game.state2": ("state", b"disc-1"),
            "states/mGBA/Game.state3": ("state", b"disc-2"),
        },
        written={
            "states/mGBA/Game.state1": (2026, 10, 7, 11, 0, 0),
            "states/mGBA/Game.state2": (2026, 10, 7, 12, 30, 0),
            "states/mGBA/Game.state3": (2026, 10, 7, 13, 30, 0),
        },
    )
    swaps = [
        session_store.DiscSwap(41, datetime(2026, 10, 7, 12, tzinfo=timezone.utc)),
        session_store.DiscSwap(42, datetime(2026, 10, 7, 13, tzinfo=timezone.utc)),
    ]
    _write, store_state = _pull_exit(
        rom, admin_user, content, disc_file_id=42, disc_swaps=swaps
    )

    discs = {c.args[4]: c.kwargs["disc_file_id"] for c in store_state.call_args_list}
    assert discs == {b"before": None, b"disc-1": 41, b"disc-2": 42}


def test_a_one_disc_session_files_every_state_on_it_whatever_the_clock(
    rom: Rom, admin_user: User
):
    """A resume restores its disc once; a broker clock behind ours must not undo it."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state1": ("state", b"slot"),
        },
        written={"states/mGBA/Game.state1": (2026, 10, 7, 11, 0, 0)},
    )
    swaps = [session_store.DiscSwap(42, datetime(2026, 10, 7, 12, tzinfo=timezone.utc))]
    _write, store_state = _pull_exit(
        rom, admin_user, content, disc_file_id=42, disc_swaps=swaps
    )

    assert store_state.call_args.kwargs["disc_file_id"] == 42


def test_a_retroarch_exit_keeps_the_zip_when_a_state_fails_to_store(
    rom: Rom, admin_user: User
):
    """The zip is the only other copy of the state, so a failed store keeps it."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"state-bytes"),
        }
    )
    _pull_exit(
        rom, admin_user, content, store_state=AsyncMock(side_effect=OSError("full"))
    )

    names = [s.file_name for s in _stored_saves(rom, admin_user)]
    assert len(names) == 2
    assert any(name.endswith(".saves.zip") for name in names)
    assert any(name.endswith(".srm") for name in names)


def test_a_retroarch_exit_with_a_save_and_no_state_files_the_save(
    rom: Rom, admin_user: User
):
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})
    _write, store_state = _pull_exit(rom, admin_user, content)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".srm")
    store_state.assert_not_awaited()


def test_a_retroarch_exit_files_every_state_slot_it_carries(rom: Rom, admin_user: User):
    """A hotkey save to another slot never went through RomM, so the archive
    is the only place it reaches the library from."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"slot-0"),
            "states/mGBA/Game.state3": ("state", b"slot-3"),
        }
    )
    _write, store_state = _pull_exit(rom, admin_user, content)

    filed = {call.args[3]: call.args[4] for call in store_state.await_args_list}
    assert filed == {"Game.state": b"slot-0", "Game.state3": b"slot-3"}


@pytest.mark.parametrize(
    ("members", "core", "emulator"),
    [
        pytest.param(
            {
                "saves/mGBA/Game.srm": ("save", b"a"),
                "saves/mGBA/Other.srm": ("save", b"b"),
            },
            "mgba",
            "retroarch",
            id="two-saves",
        ),
        pytest.param(
            {"saves/mGBA/Game.sav": ("save", b"a")}, "mgba", "retroarch", id="not-srm"
        ),
        pytest.param(
            {
                "saves/mGBA/Game.srm": ("save", b"a"),
                "memcards/card.mcd": ("memcard", b"b"),
            },
            "mgba",
            "retroarch",
            id="memory-card",
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": ("save", b"a")}, None, "retroarch", id="no-core"
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": ("save", b"a")}, "mgba", "duckstation", id="no-ra"
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": ("save", b"a")}, "../x", "retroarch", id="up-core"
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": ("save", b"a")}, "a/b", "retroarch", id="path-core"
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": ("save", b"a")},
            "c" * 51,
            "retroarch",
            id="long-core",
        ),
        pytest.param(
            {"saves/mGBA/Game.srm": (["save"], b"a")},
            "mgba",
            "retroarch",
            id="list-kind",
        ),
    ],
)
def test_an_exit_the_import_cannot_take_back_stays_a_zip(
    rom: Rom,
    admin_user: User,
    members: dict[str, tuple[Any, bytes]],
    core: str | None,
    emulator: str,
):
    """RetroArch's save import takes one .srm, so anything else keeps the
    whole archive as streaming's own restore copy."""
    content = _exit_archive(members, core=core)
    write, store_state = _pull_exit(rom, admin_user, content, emulator=emulator)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")
    assert stored.emulator == emulator
    assert write.call_args.kwargs["file"] == content
    store_state.assert_not_awaited()


def test_an_exit_member_the_manifest_does_not_list_keeps_the_zip(
    rom: Rom, admin_user: User
):
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"a")})
    buf = io.BytesIO(content)
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("saves/mGBA/stray.rtc", b"clock")
    write, _store_state = _pull_exit(rom, admin_user, buf.getvalue())

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")


def test_an_exit_archive_that_is_not_a_zip_is_still_filed(rom: Rom, admin_user: User):
    _write, _store_state = _pull_exit(rom, admin_user, b"not a zip")

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")


@pytest.mark.parametrize(
    "spec",
    [
        pytest.param(None, id="no-imports"),
        pytest.param(
            webstation.ImportSpec(
                kinds=frozenset({"state"}), state_channel="push", state_slot=None
            ),
            id="states-only",
        ),
    ],
)
def test_a_retroarch_exit_stays_a_zip_where_the_broker_takes_no_save_import(
    rom: Rom, admin_user: User, spec: webstation.ImportSpec | None
):
    """A bare save only comes back through the import, so the archive is kept."""
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})
    write, _store_state = _pull_exit(rom, admin_user, content, spec=spec)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")
    assert write.call_args.kwargs["file"] == content


def test_an_exit_archive_that_fails_to_unpack_is_still_filed(
    rom: Rom, admin_user: User
):
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})

    def corrupt_save(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
        if info.filename.endswith(".srm"):
            raise zipfile.BadZipFile("Bad CRC-32")
        return read_member(zf, info)

    with patch("handler.streaming.archive.read_member", corrupt_save):
        write, _store_state = _pull_exit(rom, admin_user, content)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")
    assert write.call_args.kwargs["file"] == content


def test_a_retroarch_exit_files_its_states_oldest_first(rom: Rom, admin_user: User):
    """The state written last heads the history, whatever the archive order."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"newer"),
            "states/mGBA/Game.state3": ("state", b"older"),
        },
        written={
            "states/mGBA/Game.state": (2026, 10, 6, 12, 0, 0),
            "states/mGBA/Game.state3": (2026, 10, 6, 11, 0, 0),
        },
    )
    _write, store_state = _pull_exit(rom, admin_user, content)

    assert [call.args[4] for call in store_state.await_args_list] == [
        b"older",
        b"newer",
    ]


def test_an_exit_state_the_history_cannot_file_keeps_the_zip(
    rom: Rom, admin_user: User
):
    """The capture stamp would push this one past the filesystem's name limit."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            f"states/mGBA/{'G' * 240}.state1": ("state", b"state-bytes"),
        }
    )
    _write, store_state = _pull_exit(rom, admin_user, content)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".saves.zip")
    store_state.assert_not_awaited()


def _pull_exit_into_history(
    rom: Rom, user: User, content: bytes, disc_file_id: int | None = None
) -> None:
    """Run an exit pull that files its states through the real state history."""

    async def scanned(**kwargs: Any) -> State:
        return _state_for(rom, user, kwargs["file_name"], kwargs["emulator"])

    with patch("handler.asset_store.scan_state", new=AsyncMock(side_effect=scanned)):
        _pull_exit(
            rom,
            user,
            content,
            disc_file_id=disc_file_id,
            store_state=AsyncMock(side_effect=states.store_state_asset),
        )


def _auto_exit(auto: bytes) -> bytes:
    return _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"slot-0"),
            "states/mGBA/Game.state.auto": ("state", auto),
        }
    )


def test_a_retroarch_exit_files_its_auto_state_with_the_rest(
    rom: Rom, admin_user: User
):
    """The auto state goes into the history, so the zip isn't kept for it."""
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    _pull_exit_into_history(rom, admin_user, _auto_exit(b"auto"), disc_file_id=disc.id)

    [stored] = _stored_saves(rom, admin_user)
    assert stored.file_name.endswith(".srm")
    history = states.user_states_for_emulator(admin_user.id, rom.id, "retroarch")
    auto = [s for s in history if s.file_name.endswith(".state.auto")]
    numbered = [s for s in history if s.file_name.endswith(".state")]
    assert len(auto) == len(numbered) == 1
    assert re.fullmatch(r"Game\.\d{8}-\d{12}\.state\.auto", auto[0].file_name)
    assert auto[0].core == "mgba"
    assert auto[0].disc_file_id == disc.id


def test_two_exits_keep_both_auto_states(rom: Rom, admin_user: User):
    _pull_exit_into_history(rom, admin_user, _auto_exit(b"first"))
    _pull_exit_into_history(rom, admin_user, _auto_exit(b"second"))

    history = states.user_states_for_emulator(admin_user.id, rom.id, "retroarch")
    autos = {s.file_name for s in history if s.file_name.endswith(".state.auto")}
    assert len(autos) == 2


def test_an_exit_with_an_auto_state_does_not_leave_the_zip_to_boot(
    rom: Rom, admin_user: User
):
    """The next launch with no pick takes the exit's .srm over an older zip."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    _pull_exit_into_history(rom, admin_user, _auto_exit(b"auto"))

    with patch(
        "handler.streaming.saves.webstation.require_import_spec",
        return_value=_SAVE_IMPORT,
    ):
        save, foreign = saves.default_save(
            admin_user.id, rom.id, _resolved(_clearing_webstation(rom))
        )
    assert save is not None and save.file_name.endswith(".srm")
    assert foreign is True


def test_a_state_check_failure_skips_only_that_state(rom: Rom, admin_user: User):
    """The unchecked state is not filed, so the zip stays as its copy."""
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state": ("state", b"slot-0"),
            "states/mGBA/Game.state3": ("state", b"slot-3"),
        }
    )
    checked = AsyncMock(side_effect=[OSError("unreadable"), None])
    with patch("handler.streaming.saves.states.stored_copy", checked):
        _write, store_state = _pull_exit(rom, admin_user, content)

    names = [s.file_name for s in _stored_saves(rom, admin_user)]
    assert sorted(name.endswith(".srm") for name in names) == [False, True]
    assert any(name.endswith(".saves.zip") for name in names)
    store_state.assert_awaited_once()


def test_an_unchanged_raw_save_is_not_filed_twice(rom: Rom, admin_user: User):
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})
    _add_save(rom, admin_user, "Game [old].srm", "mgba", "same", slot=AUTOSAVE_SLOT)

    async def scanned(**kwargs: Any) -> Save:
        return _save_for(rom, admin_user, kwargs["file_name"], "mgba", "same")

    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=content),
        patch(
            "handler.streaming.saves.webstation.import_spec", return_value=_SAVE_IMPORT
        ),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.streaming.saves.scan_save", new=AsyncMock(side_effect=scanned)),
        patch("handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()) as rm,
    ):
        assert asyncio.run(
            saves.pull_saves_to_library(
                admin_user.id, rom.id, _resolved(_clearing_webstation(rom))
            )
        )
    rm.assert_awaited_once()
    assert [s.file_name for s in _stored_saves(rom, admin_user)] == ["Game [old].srm"]


def test_an_older_slot_from_the_exit_files_under_the_exit_capture(
    rom: Rom, admin_user: User
):
    """Teardown filed the exit's own state first, so it still heads the history."""
    exit_capture = _add_state(
        rom, admin_user, "Game.20261006-120000000000.state.auto", "retroarch"
    )
    content = _exit_archive(
        {
            "saves/mGBA/Game.srm": ("save", b"eeprom"),
            "states/mGBA/Game.state3": ("state", b"slot-3"),
            "states/mGBA/Game.state.auto": ("state", b"auto"),
        },
        written={
            "states/mGBA/Game.state3": (2026, 10, 6, 11, 0, 0),
            "states/mGBA/Game.state.auto": (2026, 10, 6, 12, 0, 0),
        },
    )

    async def stored(_user: int, _rom: int, _emulator: str, data: bytes) -> Any:
        return exit_capture if data == b"auto" else None

    with patch("handler.streaming.saves.states.stored_copy", side_effect=stored):
        _pull_exit_into_history(rom, admin_user, content)

    history = states.user_states_for_emulator(admin_user.id, rom.id, "retroarch")
    assert [s.id for s in history][0] == exit_capture.id
    assert len(history) == 2
    assert history[1].file_name.endswith(".state3")


def _pull_raw_exit_save(rom: Rom, user: User, content_hash: str) -> AsyncMock:
    """Pull a one-`.srm` exit whose save hashes to `content_hash`."""
    content = _exit_archive({"saves/mGBA/Game.srm": ("save", b"eeprom")})

    async def scanned(**kwargs: Any) -> Save:
        return _save_for(rom, user, kwargs["file_name"], "mgba", content_hash)

    with (
        patch("handler.streaming.saves.fetch_save_archive", return_value=content),
        patch(
            "handler.streaming.saves.webstation.import_spec", return_value=_SAVE_IMPORT
        ),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.streaming.saves.scan_save", new=AsyncMock(side_effect=scanned)),
        patch("handler.filesystem.fs_asset_handler.remove_file", new=AsyncMock()) as rm,
    ):
        assert asyncio.run(
            saves.pull_saves_to_library(
                user.id, rom.id, _resolved(_clearing_webstation(rom))
            )
        )
    return rm


def test_an_exit_back_on_an_older_save_boots_that_save_next(rom: Rom, admin_user: User):
    """The player loaded A after B and quit with A's bytes unchanged."""
    older = _add_save(
        rom, admin_user, "Game [a].srm", "mgba", "same", slot=AUTOSAVE_SLOT
    )
    newer = _add_save(
        rom, admin_user, "Game [b].srm", "mgba", "other", slot=AUTOSAVE_SLOT
    )
    _stamp(
        older,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    _stamp(
        newer,
        datetime(2026, 10, 2, tzinfo=timezone.utc),
        datetime(2026, 10, 2, tzinfo=timezone.utc),
    )

    rm = _pull_raw_exit_save(rom, admin_user, "same")

    rm.assert_not_awaited()
    with patch(
        "handler.streaming.saves.webstation.require_import_spec",
        return_value=_SAVE_IMPORT,
    ):
        save, _foreign = saves.default_save(
            admin_user.id, rom.id, _resolved(_clearing_webstation(rom))
        )
    assert save is not None
    assert save.id not in (older.id, newer.id)
    assert save.content_hash == "same"


def test_an_exit_matching_only_a_missing_save_keeps_its_copy(
    rom: Rom, admin_user: User
):
    gone = _add_save(
        rom, admin_user, "Game [a].srm", "mgba", "same", slot=AUTOSAVE_SLOT
    )
    with sync_session.begin() as session:
        session.execute(
            update(Save).where(Save.id == gone.id).values(missing_from_fs=True)
        )

    rm = _pull_raw_exit_save(rom, admin_user, "same")

    rm.assert_not_awaited()
    assert len(_stored_saves(rom, admin_user)) == 2


def test_an_exit_matching_the_slot_head_under_an_alias_adds_no_version(
    rom: Rom, admin_user: User
):
    """Cloud Sync reads the slot across the folder's aliases, so a head filed
    under RetroArch's own folder name is the save the exit brought back."""
    _add_save(rom, admin_user, "Game [a].srm", "mGBA", "same", slot=AUTOSAVE_SLOT)

    rm = _pull_raw_exit_save(rom, admin_user, "same")

    rm.assert_awaited_once()
    assert len(_stored_saves(rom, admin_user)) == 1


# ── A launch with no pick boots the newest save, raw or zipped ────────────────


def _claim_without_a_pick(
    client,
    token,
    rom: Rom,
    spec: Any,
    imported: imports.ImportHydration | None = None,
) -> tuple[Any, AsyncMock, AsyncMock, Any]:
    """Claim with no save pick, returning the response, both hydration mocks,
    and the session record the claim left behind."""
    hydrate_import = AsyncMock(
        return_value=imported or imports.ImportHydration("rom-1.zip", False)
    )
    hydrate_native = AsyncMock(return_value="/config/native.zip")
    require = (
        MagicMock(side_effect=spec)
        if isinstance(spec, Exception)
        else MagicMock(return_value=spec)
    )
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", return_value={"url": "/r"}),
            patch("handler.streaming.saves.webstation.require_import_spec", require),
            patch("handler.streaming.imports.hydrate_import_archive", hydrate_import),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", hydrate_native
            ),
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            resp = _claim(client, token, rom.id)
        session = _session_raw(_clearing_webstation(rom))
    return resp, hydrate_import, hydrate_native, session


def test_a_launch_with_no_pick_imports_a_raw_save_newer_than_the_archive(
    client, access_token, rom: Rom, admin_user: User
):
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    raw = _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, _SAVE_IMPORT
    )

    assert resp.status_code == 202
    hydrate_import.assert_awaited_once()
    assert hydrate_import.call_args.kwargs["save"].id == raw.id
    assert hydrate_import.call_args.kwargs["save_is_foreign"] is True
    hydrate_native.assert_not_awaited()


def test_a_launch_with_no_pick_restores_the_archive_when_the_raw_save_fails_to_import(
    client, access_token, rom: Rom, admin_user: User
):
    """The raw save was only the default, so the newest archive still boots."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, _SAVE_IMPORT, imported=imports.ImportHydration()
    )

    assert resp.status_code == 202
    hydrate_import.assert_awaited_once()
    hydrate_native.assert_awaited_once()
    assert hydrate_native.call_args.args[3] is None


def _refused_save(member: str) -> broker.ImportRefusedError:
    return broker.ImportRefusedError(
        [
            ImportRefusalSchema(
                reason="destination_conflict",
                member=member,
                expected=None,
                detail=None,
                suggest_emulator=None,
                docs=None,
            )
        ],
        0,
    )


def _claim_refused_once(
    client, token, rom: Rom, refused: broker.ImportRefusedError, save_id: int | None
) -> tuple[Any, MagicMock, AsyncMock, list[tuple[str, dict[str, Any]]]]:
    """Claim against a broker that refuses the first activate's import."""
    activate = MagicMock(side_effect=[refused, {"url": "/r"}])
    hydrate_native = AsyncMock(return_value="/config/native.zip")
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.webstation.require_import_spec",
                return_value=_SAVE_IMPORT,
            ),
            patch(
                "handler.streaming.imports.hydrate_import_archive",
                new=AsyncMock(return_value=imports.ImportHydration("rom-1.zip")),
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", hydrate_native
            ),
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            with _pushes() as sent:
                resp = _claim(client, token, rom.id, save_id=save_id)
    return resp, activate, hydrate_native, sent


def test_a_launch_with_no_pick_boots_the_archive_when_the_broker_refuses_the_raw_save(
    client, access_token, rom: Rom, admin_user: User
):
    """The broker refuses an import at activate, after the upload went through."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, activate, hydrate_native, sent = _claim_refused_once(
        client, access_token, rom, _refused_save(".import/save/Game.srm"), None
    )

    assert resp.status_code == 202
    assert [event for event, _ in sent] == ["streaming:launch-ready"]
    assert [c.kwargs["archive_path"] for c in activate.call_args_list] == [
        "rom-1.zip",
        "/config/native.zip",
    ]
    hydrate_native.assert_awaited_once()


def test_a_refused_raw_save_the_player_picked_still_fails_the_launch(
    client, access_token, rom: Rom, admin_user: User
):
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    raw = _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, activate, hydrate_native, sent = _claim_refused_once(
        client, access_token, rom, _refused_save(".import/save/Game.srm"), raw.id
    )

    assert resp.status_code == 202
    assert [event for event, _ in sent] == ["streaming:launch-failed"]
    activate.assert_called_once()
    hydrate_native.assert_not_awaited()


def test_a_launch_with_no_pick_restores_an_archive_newer_than_the_raw_save(
    client, access_token, rom: Rom, admin_user: User
):
    _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h1")
    _add_save(rom, admin_user, "Game [retroarch b].saves.zip", "retroarch", "h2")

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, _SAVE_IMPORT
    )

    assert resp.status_code == 202
    hydrate_import.assert_not_awaited()
    hydrate_native.assert_awaited_once()


def _stamp(save: Save, created_at: datetime, updated_at: datetime) -> None:
    with sync_session.begin() as session:
        session.execute(
            update(Save)
            .where(Save.id == save.id)
            .values(created_at=created_at, updated_at=updated_at)
        )


def test_a_launch_with_no_pick_imports_a_raw_save_written_since_the_archive(
    client, access_token, rom: Rom, admin_user: User
):
    """The web player writes into its row, so only updated_at shows the play."""
    raw = _add_save(rom, admin_user, "Game.srm", "mgba", "h1")
    zipped = _add_save(
        rom, admin_user, "Game [retroarch b].saves.zip", "retroarch", "h2"
    )
    _stamp(
        raw,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 3, tzinfo=timezone.utc),
    )
    _stamp(
        zipped,
        datetime(2026, 10, 2, tzinfo=timezone.utc),
        datetime(2026, 10, 2, tzinfo=timezone.utc),
    )

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, _SAVE_IMPORT
    )

    assert resp.status_code == 202
    hydrate_import.assert_awaited_once()
    assert hydrate_import.call_args.kwargs["save"].id == raw.id
    hydrate_native.assert_not_awaited()


def _mark_missing(save: Save, updated_at: datetime) -> None:
    """What RetroArch sync leaves on a row whose file vanished."""
    with sync_session.begin() as session:
        session.execute(
            update(Save)
            .where(Save.id == save.id)
            .values(missing_from_fs=True, updated_at=updated_at)
        )


def test_a_launch_with_no_pick_skips_a_raw_save_whose_file_is_missing(
    client, access_token, rom: Rom, admin_user: User
):
    zipped = _add_save(
        rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1"
    )
    raw = _add_save(rom, admin_user, "Game.srm", "mgba", "h2")
    _mark_missing(raw, datetime(2030, 1, 1, tzinfo=timezone.utc))

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, _SAVE_IMPORT
    )

    assert resp.status_code == 202
    hydrate_import.assert_not_awaited()
    hydrate_native.assert_awaited_once()
    assert hydrate_native.call_args.args[3].id == zipped.id


def test_newest_restorable_skips_an_archive_whose_file_is_missing(
    rom: Rom, admin_user: User
):
    kept = _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    gone = _add_save(rom, admin_user, "Game [retroarch b].saves.zip", "retroarch", "h2")
    _mark_missing(gone, datetime(2030, 1, 1, tzinfo=timezone.utc))

    newest = saves.newest_restorable(admin_user.id, rom.id, "retroarch")

    assert newest is not None and newest.id == kept.id


def test_a_launch_with_no_pick_reads_an_upper_case_zip_as_an_archive(
    client, access_token, rom: Rom, admin_user: User
):
    zipped = _add_save(rom, admin_user, "GAME.ZIP", "retroarch", "h1")

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, None
    )

    assert resp.status_code == 202
    hydrate_native.assert_awaited_once()
    assert hydrate_native.call_args.args[3].id == zipped.id


def test_a_launch_with_no_pick_restores_the_archive_where_saves_cannot_import(
    client, access_token, rom: Rom, admin_user: User
):
    """A broker that declares no save import would refuse the raw save at
    activate, so the archive it can restore is the one sent."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, hydrate_import, hydrate_native, _session = _claim_without_a_pick(
        client, access_token, rom, None
    )

    assert resp.status_code == 202
    hydrate_import.assert_not_awaited()
    hydrate_native.assert_awaited_once()


def test_a_launch_with_no_pick_asks_for_a_retry_when_the_raw_save_cannot_be_checked(
    client, access_token, rom: Rom, admin_user: User
):
    """Booting the older archive instead would roll the player's game back."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    _add_save(rom, admin_user, "Game [2026-10-06_10-00-00].srm", "mgba", "h2")

    resp, hydrate_import, hydrate_native, session = _claim_without_a_pick(
        client, access_token, rom, webstation.ImportSpecUnavailable()
    )

    assert resp.status_code == 503
    hydrate_import.assert_not_awaited()
    hydrate_native.assert_not_awaited()
    assert session is None


def test_hydrate_saves_pushes_newest_matching_zip(rom: Rom, admin_user: User):
    """Hydration pushes the newest .zip save for this container's emulator, and
    ignores non-zip saves and other emulators' saves."""
    _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    newest = _add_save(rom, admin_user, "Game [pcsx2 b].saves.zip", "pcsx2", "h2")
    _add_save(rom, admin_user, "loose.mcr", "pcsx2", "h3")
    _add_save(rom, admin_user, "Game [dolphin].saves.zip", "dolphin", "h4")
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        # Path-derived bytes, so the assertion below names which of the four
        # saves was actually read rather than just that something was pushed.
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=lambda path: path.encode()),
        ),
        patch("handler.streaming.saves.push_save_archive", return_value=True) as push,
    ):
        ok = asyncio.run(
            saves.hydrate_saves_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert ok is True
    push.assert_called_once()
    # The newest pcsx2 .zip, never the .mcr, the dolphin save, or the older zip.
    assert push.call_args[0][1] == newest.full_path.encode()


def test_hydrate_saves_no_matching_save_returns_false(rom: Rom, admin_user: User):
    """No stored zip save for the emulator means nothing to hydrate."""
    _add_save(rom, admin_user, "loose.mcr", "pcsx2", "h1")
    container = {**_container_for(rom), "label": "PCSX2"}
    with patch("handler.streaming.saves.push_save_archive", return_value=True) as push:
        ok = asyncio.run(
            saves.hydrate_saves_to_broker(admin_user.id, rom.id, _resolved(container))
        )
    assert ok is False
    push.assert_not_called()


def _clearing_webstation(rom: Rom) -> dict[str, Any]:
    """A webstation container whose emulator empties the save tree before a
    restore, the only kind that honours a pick other than the newest."""
    return {
        **_container_for(rom),
        "protocol": "webstation",
        "emulator": "retroarch",
    }


def _three_archives(rom: Rom, user: User) -> list[Save]:
    """Three stored retroarch archives, oldest first."""
    return [
        _add_save(rom, user, f"Game [retroarch {tag}].saves.zip", "retroarch", tag)
        for tag in ("a", "b", "c")
    ]


def test_hydrate_saves_uploads_the_picked_archive(rom: Rom, admin_user: User):
    """A pick is restored even when a newer archive exists."""
    oldest, _, _ = _three_archives(rom, admin_user)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=lambda path: path.encode()),
        ),
        patch(
            "handler.streaming.webstation.upload_archive", return_value="/config/x.zip"
        ) as upload,
    ):
        path = asyncio.run(
            saves.hydrate_saves_to_webstation(
                admin_user.id,
                rom.id,
                _resolved(_clearing_webstation(rom)),
                oldest,
            )
        )
    assert path == "/config/x.zip"
    assert upload.call_args[0][2] == oldest.full_path.encode()


def test_hydrate_saves_without_a_pick_uploads_the_newest(rom: Rom, admin_user: User):
    """No pick keeps the behaviour every container had before the picker."""
    *_, newest = _three_archives(rom, admin_user)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=lambda path: path.encode()),
        ),
        patch(
            "handler.streaming.webstation.upload_archive", return_value="/config/x.zip"
        ) as upload,
    ):
        asyncio.run(
            saves.hydrate_saves_to_webstation(
                admin_user.id, rom.id, _resolved(_clearing_webstation(rom))
            )
        )
    assert upload.call_args[0][2] == newest.full_path.encode()


def test_hydrate_saves_uploads_nothing_when_the_pick_left_the_disk(
    rom: Rom, admin_user: User
):
    """Deleted between the pick and the claim. Falling back to the newest would
    restore a save the player did not choose, so the launch gets none."""
    oldest, _, _ = _three_archives(rom, admin_user)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("handler.streaming.webstation.upload_archive") as upload,
    ):
        path = asyncio.run(
            saves.hydrate_saves_to_webstation(
                admin_user.id, rom.id, _resolved(_clearing_webstation(rom)), oldest
            )
        )
    assert path is None
    upload.assert_not_called()


def test_resolve_save_archive_accepts_the_players_own_archive(
    rom: Rom, admin_user: User
):
    """The happy path the launch screen's picker produces."""
    archive = _add_save(
        rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1"
    )
    resolved, is_foreign = saves.resolve_save_archive(
        admin_user.id, rom, _resolved(_clearing_webstation(rom)), archive.id
    )
    assert resolved.id == archive.id
    assert is_foreign is False


def test_resolve_save_archive_rejects_a_save_that_is_not_the_players(
    rom: Rom, admin_user: User, viewer_user: User
):
    """Saves are private, so another player's archive must not be nameable."""
    theirs = _add_save(
        rom, viewer_user, "Game [retroarch a].saves.zip", "retroarch", "h1"
    )
    with pytest.raises(HTTPException) as exc:
        saves.resolve_save_archive(
            admin_user.id, rom, _resolved(_clearing_webstation(rom)), theirs.id
        )
    assert exc.value.status_code == 404


def test_resolve_save_archive_rejects_a_save_from_another_rom(
    rom: Rom, second_rom: Rom, admin_user: User
):
    """The pick is scoped to the ROM being launched, so the player's own
    archive for a different game is as unnameable as someone else's."""
    elsewhere = _add_save(
        second_rom, admin_user, "Other [retroarch a].saves.zip", "retroarch"
    )
    with pytest.raises(HTTPException) as exc:
        saves.resolve_save_archive(
            admin_user.id, rom, _resolved(_clearing_webstation(rom)), elsewhere.id
        )
    assert exc.value.status_code == 404


def test_resolve_save_archive_rejects_another_emulators_archive(
    rom: Rom, admin_user: User
):
    """Another emulator's archive lays its members out where this one never
    reads, so the restore would write files the game never opens."""
    other = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    with patch(
        "handler.streaming.saves.webstation.require_import_spec", return_value=None
    ):
        with pytest.raises(HTTPException) as exc:
            saves.resolve_save_archive(
                admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Save was made by a different emulator"


def test_resolve_save_archive_rejects_a_bare_save_file(rom: Rom, admin_user: User):
    """A loose save carries no layout the broker could restore it from."""
    loose = _add_save(rom, admin_user, "Game.srm", "retroarch", "h1")
    with patch(
        "handler.streaming.saves.webstation.require_import_spec", return_value=None
    ):
        with pytest.raises(HTTPException) as exc:
            saves.resolve_save_archive(
                admin_user.id, rom, _resolved(_clearing_webstation(rom)), loose.id
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Save is not a restorable archive"


def test_resolve_save_archive_asks_for_a_retry_when_the_broker_did_not_answer(
    rom: Rom, admin_user: User
):
    """A bare save whose import check timed out asks the player to try again."""
    loose = _add_save(rom, admin_user, "Game.srm", "mgba", "h1")
    with patch(
        "handler.streaming.saves.webstation.require_import_spec",
        side_effect=webstation.ImportSpecUnavailable,
    ):
        with pytest.raises(HTTPException) as exc:
            saves.resolve_save_archive(
                admin_user.id, rom, _resolved(_clearing_webstation(rom)), loose.id
            )
    assert exc.value.status_code == 503


def test_resolve_save_archive_rejects_a_pick_where_it_would_not_land(
    rom: Rom, admin_user: User
):
    """An emulator that keeps the container's own save files skips any member
    it already holds a newer copy of, so honouring the pick would be a lie."""
    archive = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    with pytest.raises(HTTPException) as exc:
        saves.resolve_save_archive(
            admin_user.id, rom, _resolved(_webstation_for(rom)), archive.id
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "This emulator always restores the newest save"


def test_resolve_save_archive_accepts_a_foreign_pick_the_broker_will_import(
    rom: Rom, admin_user: User
):
    """A pick that fails the native check is not turned away outright: it is
    checked against the broker's own import-spec first."""
    other = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    spec = webstation.ImportSpec(
        kinds=frozenset({"save"}),
        state_channel="archive",
        state_slot=0,
    )
    with patch(
        "handler.streaming.saves.webstation.require_import_spec", return_value=spec
    ):
        save, is_foreign = saves.resolve_save_archive(
            admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
        )
    assert save.id == other.id
    assert is_foreign is True


def test_resolve_save_archive_still_refuses_when_the_broker_has_no_import_spec(
    rom: Rom, admin_user: User
):
    other = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    with patch(
        "handler.streaming.saves.webstation.require_import_spec", return_value=None
    ):
        with pytest.raises(HTTPException) as exc:
            saves.resolve_save_archive(
                admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Save was made by a different emulator"


def test_resolve_resume_state_asks_for_a_retry_when_the_broker_did_not_answer(
    rom: Rom, admin_user: User
):
    """A foreign state whose import check timed out asks the player to try again."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    with patch(
        "handler.streaming.states.webstation.require_import_spec",
        side_effect=webstation.ImportSpecUnavailable,
    ):
        with pytest.raises(HTTPException) as exc:
            states.resolve_resume_state(
                admin_user.id, rom, _resolved(_webstation_for(rom)), state.id
            )
    assert exc.value.status_code == 503


def test_resolve_resume_state_accepts_the_players_own_state(rom: Rom, admin_user: User):
    state = _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    resolved, slot, is_foreign = states.resolve_resume_state(
        admin_user.id, rom, _resolved(_webstation_for(rom)), state.id
    )
    assert resolved.id == state.id
    assert slot == 1
    assert is_foreign is False


def test_resolve_resume_state_resumes_an_auto_state_from_the_working_slot(
    rom: Rom, admin_user: User
):
    """The broker files any pushed state into its working slot, so a native
    auto state needs no import check."""
    auto = _core_state(rom, admin_user, "Game.20260202-000000000000.state.auto", None)
    with (
        patch("handler.streaming.webstation.default_core", return_value=None),
        patch("handler.streaming.states.webstation.require_import_spec") as require,
    ):
        resolved, slot, is_foreign = states.resolve_resume_state(
            admin_user.id, rom, _snes("retroarch"), auto.id
        )
    assert (resolved.id, slot, is_foreign) == (auto.id, 0, False)
    require.assert_not_called()


def test_resolve_resume_state_rejects_a_state_that_is_not_visible(
    rom: Rom, admin_user: User, viewer_user: User
):
    state = _add_state(rom, viewer_user, "Game.01.p2s", "pcsx2")
    with pytest.raises(HTTPException) as exc:
        states.resolve_resume_state(
            admin_user.id, rom, _resolved(_webstation_for(rom)), state.id
        )
    assert exc.value.status_code == 404


def test_resolve_resume_state_accepts_a_foreign_pick_on_an_archive_channel(
    rom: Rom, admin_user: User
):
    """A pick from an emulator the container does not natively read is not
    turned away: the broker's import-spec supplies the slot to resume from."""
    other = _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="archive",
        state_slot=2,
    )
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=spec
    ):
        resolved, slot, is_foreign = states.resolve_resume_state(
            admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
        )
    assert resolved.id == other.id
    assert slot == 2
    assert is_foreign is True


def test_resolve_resume_state_accepts_a_foreign_pick_on_a_push_channel(
    rom: Rom, admin_user: User
):
    other = _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="push",
        state_slot=1,
    )
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=spec
    ):
        resolved, slot, is_foreign = states.resolve_resume_state(
            admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
        )
    assert slot == 1
    assert is_foreign is True


def test_resolve_resume_state_refuses_a_foreign_pick_when_the_channel_is_none(
    rom: Rom, admin_user: User
):
    other = _add_state(rom, admin_user, "Game.01.p2s", "pcsx2")
    spec = webstation.ImportSpec(
        kinds=frozenset(), state_channel="none", state_slot=None
    )
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=spec
    ):
        with pytest.raises(HTTPException) as exc:
            states.resolve_resume_state(
                admin_user.id, rom, _resolved(_clearing_webstation(rom)), other.id
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "State was made by a different emulator"


def test_resolve_resume_state_rejects_an_unrecognized_slot_when_no_import_spec(
    rom: Rom, admin_user: User
):
    """A same-emulator state whose filename carries no slot, and no broker
    import-spec to fall back on, is refused for its slot."""
    weird = _add_state(rom, admin_user, "Game.state", "pcsx2")
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=None
    ):
        with pytest.raises(HTTPException) as exc:
            states.resolve_resume_state(
                admin_user.id, rom, _resolved(_webstation_for(rom)), weird.id
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "State filename carries no recognizable slot number"


def test_origin_of_tags_a_device_capture_as_hardware():
    assert imports.origin_of("retroarch", "device-123") == "hardware"


def test_origin_of_tags_an_untagged_save_as_unknown():
    assert imports.origin_of(None, None) == "unknown"
    assert imports.origin_of("", None) == "unknown"


def test_origin_of_tags_a_streaming_emulator_as_standalone():
    assert imports.origin_of("retroarch", None) == "standalone"


def test_origin_of_tags_anything_else_as_emulatorjs():
    assert imports.origin_of("mgba-wasm", None) == "emulatorjs"


def test_build_import_archive_wraps_a_foreign_save_with_no_base():
    """A foreign save pick with no native base builds a fresh zip: no v1
    entries to carry over, one `.import/save/...` member."""
    member = imports.ForeignMember(
        kind="save", name="Game.srm", content=b"save-bytes", origin="standalone"
    )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=None, members=[member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert ".import/save/Game.srm" in names
        assert zf.read(".import/save/Game.srm") == b"save-bytes"
        manifest = json.loads(zf.read(".broker-manifest.json"))
    assert manifest["version"] == 2
    assert manifest["import"] == {"source": "romm", "rom_id": 7}
    assert manifest["files"] == [
        {"path": ".import/save/Game.srm", "kind": "save", "origin": "standalone"}
    ]


def test_build_import_archive_expands_a_foreign_zips_own_members():
    """A foreign pick that is itself a zip has its members unpacked under the
    import prefix, not nested as a zip-within-zip."""
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as izf:
        izf.writestr("save.mcr", b"card-bytes")
    member = imports.ForeignMember(
        kind="save", name="Game.saves.zip", content=inner.getvalue(), origin="hardware"
    )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=None, members=[member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert ".import/save/save.mcr" in zf.namelist()
        assert zf.read(".import/save/save.mcr") == b"card-bytes"


def test_build_import_archive_keeps_a_zip_shaped_state_whole():
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as izf:
        izf.writestr("eeMemory.bin", b"ee-bytes")
    member = imports.ForeignMember(
        kind="state",
        name="SLUS-20062 (ABCD1234).01.p2s",
        content=inner.getvalue(),
        origin="standalone",
    )
    zip_bytes, carried = imports.build_import_archive(
        rom_id=7, base=None, members=[member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert zf.read(".import/state/SLUS-20062 (ABCD1234).01.p2s") == inner.getvalue()
    assert [f["path"] for f in carried] == [
        ".import/state/SLUS-20062 (ABCD1234).01.p2s"
    ]


def test_build_import_archive_names_a_carried_entry_by_its_staged_path():
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        bzf.writestr("saves\\Game.srm", b"native-save-bytes")
        bzf.writestr(
            ".broker-manifest.json",
            json.dumps(
                {"version": 1, "files": [{"path": "saves\\Game.srm", "kind": "save"}]}
            ),
        )
    _zip_bytes, carried = imports.build_import_archive(
        rom_id=7,
        base=("Game.saves.zip", base_zip.getvalue()),
        members=[
            imports.ForeignMember(
                kind="state", name="Game.00.pcsx2", content=b"s", origin="standalone"
            )
        ],
    )
    assert {"path": "saves/Game.srm", "kind": "save"} in carried


def test_build_import_archive_keeps_a_native_base_alongside_a_foreign_state():
    """One native save and one foreign state in the same launch: the save
    stays entirely on its own v1 entry, only the state gets an import
    member. This is the mixed-kind case Appendix A(e) describes."""
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        bzf.writestr("Game.srm", b"native-save-bytes")
        bzf.writestr(
            ".broker-manifest.json",
            json.dumps({"version": 1, "files": [{"path": "Game.srm", "kind": "save"}]}),
        )
    state_member = imports.ForeignMember(
        kind="state", name="Game.00.pcsx2", content=b"state-bytes", origin="standalone"
    )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=("Game.saves.zip", base_zip.getvalue()), members=[state_member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "Game.srm" in names
        assert zf.read("Game.srm") == b"native-save-bytes"
        assert ".import/state/Game.00.pcsx2" in names
        manifest = json.loads(zf.read(".broker-manifest.json"))
    assert manifest["version"] == 2
    paths = {f["path"] for f in manifest["files"]}
    assert paths == {"Game.srm", ".import/state/Game.00.pcsx2"}


def test_build_import_archive_strips_the_bases_own_state_member_when_importing_a_foreign_state():
    """The base's own v1 state entry is stripped whenever a foreign state
    rides in the same zip, so the two never collide on the emulator's one
    state slot."""
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        bzf.writestr("Game.srm", b"native-save-bytes")
        bzf.writestr("Game.00.pcsx2", b"native-state-bytes")
        bzf.writestr(
            ".broker-manifest.json",
            json.dumps(
                {
                    "version": 1,
                    "files": [
                        {"path": "Game.srm", "kind": "save"},
                        {"path": "Game.00.pcsx2", "kind": "state"},
                    ],
                }
            ),
        )
    state_member = imports.ForeignMember(
        kind="state",
        name="Game.00.dolphin",
        content=b"foreign-state",
        origin="standalone",
    )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=("Game.saves.zip", base_zip.getvalue()), members=[state_member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "Game.srm" in names
        assert "Game.00.pcsx2" not in names
        assert ".import/state/Game.00.dolphin" in names


def test_build_import_archive_leaves_a_foreign_save_archives_own_state_out():
    """Another emulator's save archive also carries its exit state, which a
    save pick must not import as a save."""
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as izf:
        izf.writestr("memcards/Game.mcd", b"card-bytes")
        izf.writestr("savestates/Game.sav", b"state-bytes")
        izf.writestr(
            ".broker-manifest.json",
            json.dumps(
                {
                    "version": 1,
                    "files": [
                        {"path": "memcards/Game.mcd", "kind": "save"},
                        {"path": "savestates/Game.sav", "kind": "state"},
                    ],
                }
            ),
        )
    member = imports.ForeignMember(
        kind="save",
        name="Game [duckstation a].saves.zip",
        content=inner.getvalue(),
        origin="standalone",
    )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=None, members=[member]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert ".import/save/memcards/Game.mcd" in names
    assert not any(name.endswith("Game.sav") for name in names)


def test_build_import_archive_keeps_a_base_members_timestamp():
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        bzf.writestr(
            zipfile.ZipInfo("Game.srm", date_time=(2024, 1, 2, 3, 4, 6)), b"native"
        )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7,
        base=("Game.saves.zip", base_zip.getvalue()),
        members=[
            imports.ForeignMember(
                kind="state", name="Game.00.pcsx2", content=b"s", origin="standalone"
            )
        ],
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert zf.getinfo("Game.srm").date_time == (2024, 1, 2, 3, 4, 6)


def test_build_import_archive_strips_dotfiles_and_macosx_junk():
    from tests._zipfile_shim import reload_zipfile

    # zipfile-inflate64 in the import chain breaks writestr; restore stdlib first.
    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        bzf.writestr("Game.srm", b"native-save-bytes")
        bzf.writestr("__MACOSX/._Game.srm", b"junk")
        bzf.writestr(".DS_Store", b"junk")
        bzf.writestr(
            ".broker-manifest.json",
            json.dumps({"version": 1, "files": [{"path": "Game.srm", "kind": "save"}]}),
        )
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7,
        base=("Game.saves.zip", base_zip.getvalue()),
        members=[
            imports.ForeignMember(
                kind="state", name="Game.00.pcsx2", content=b"s", origin="standalone"
            )
        ],
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert not any(
            "__MACOSX" in n
            or n.split("/")[-1].startswith(".")
            and n != ".broker-manifest.json"
            for n in names
        )


def test_archive_budget_charges_bytes_and_members():
    budget = imports._ArchiveBudget(bytes_left=10, members_left=2)
    budget.charge(4)
    assert budget.bytes_left == 6
    assert budget.members_left == 1


def test_archive_budget_raises_once_the_byte_budget_is_exceeded():
    budget = imports._ArchiveBudget(bytes_left=10, members_left=2000)
    with pytest.raises(ValueError):
        budget.charge(11)


def test_archive_budget_raises_once_the_member_budget_is_exceeded():
    budget = imports._ArchiveBudget(bytes_left=1_000_000, members_left=1)
    budget.charge(1)
    with pytest.raises(ValueError):
        budget.charge(1)


def test_build_import_archive_rejects_a_foreign_member_over_the_expanded_byte_budget():
    """A member's own byte length is charged before it is staged, so an
    oversized upload is rejected rather than fully expanded in memory."""
    member = imports.ForeignMember(
        kind="save", name="Game.srm", content=b"x" * 10, origin="standalone"
    )
    real_budget = imports._ArchiveBudget
    with patch(
        "handler.streaming.imports._ArchiveBudget",
        lambda: real_budget(bytes_left=5, members_left=2000),
    ):
        with pytest.raises(ValueError):
            imports.build_import_archive(rom_id=7, base=None, members=[member])


def _understated_zip(name: str, content: bytes, declared_size: int) -> bytes:
    """A one-entry zip whose central directory understates the entry's size."""
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, content)
    raw = bytearray(buf.getvalue())
    central = raw.rindex(b"PK\x01\x02")
    raw[central + 24 : central + 28] = declared_size.to_bytes(4, "little")
    return bytes(raw)


def test_build_import_archive_does_not_inflate_past_a_members_declared_size():
    import tracemalloc

    bomb = _understated_zip("Game.srm", b"\0" * (64 * 1024 * 1024), 16)
    tracemalloc.start()
    try:
        with pytest.raises(zipfile.BadZipFile):
            imports.build_import_archive(
                rom_id=7, base=("Game.saves.zip", bomb), members=[]
            )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 16 * 1024 * 1024


def test_manifest_files_rejects_a_manifest_over_the_size_cap():
    """Dropping it would lose which entries are states, so a replaced state
    would ride along as a save."""
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    manifest = {"files": [{"path": "Game.srm", "kind": "save"}], "pad": "x" * 64}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(".broker-manifest.json", json.dumps(manifest))
    with (
        patch("handler.streaming.archive.MAX_MANIFEST_BYTES", 32),
        zipfile.ZipFile(buf) as zf,
        pytest.raises(ValueError),
    ):
        imports._manifest_files(zf)


def test_build_import_archive_rebuilds_a_symlink_entry_as_a_regular_file():
    import stat

    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    base_zip = io.BytesIO()
    with zipfile.ZipFile(base_zip, "w") as bzf:
        link = zipfile.ZipInfo("Game.srm")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bzf.writestr(link, b"/etc/passwd")
    zip_bytes, _carried = imports.build_import_archive(
        rom_id=7, base=("Game.saves.zip", base_zip.getvalue()), members=[]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        mode = zf.getinfo("Game.srm").external_attr >> 16
    assert stat.S_ISREG(mode)
    assert stat.S_IMODE(mode) == 0o777


def test_hydrate_import_archive_uploads_a_foreign_save_with_no_native_base(
    rom: Rom, admin_user: User
):
    save = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    upload = MagicMock(return_value="rom-1.zip")
    with (
        patch(
            "handler.streaming.imports.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"picked-bytes"),
        ),
        patch("handler.streaming.imports.webstation.upload_archive", upload),
    ):
        result = asyncio.run(
            imports.hydrate_import_archive(
                admin_user.id,
                rom,
                _resolved(_clearing_webstation(rom)),
                save=save,
                save_is_foreign=True,
                state=None,
            )
        )
    assert result.path == "rom-1.zip"
    assert result.state_imported is False
    upload.assert_called_once()
    uploaded_bytes = upload.call_args.args[2]
    with zipfile.ZipFile(io.BytesIO(uploaded_bytes)) as zf:
        assert f".import/save/{save.file_name}" in zf.namelist()


def test_hydrate_import_archive_falls_back_to_the_newest_native_save_as_base(
    rom: Rom, admin_user: User
):
    """A state-only foreign pick (no save_id) still carries the newest
    native save as the base, as a launch with no pick does."""
    _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    state = _add_state(rom, admin_user, "Game.00.pcsx2", "pcsx2")
    upload = MagicMock(return_value="rom-1.zip")
    with (
        patch(
            "handler.streaming.imports.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=lambda path: path.encode()),
        ),
        patch("handler.streaming.imports.webstation.upload_archive", upload),
    ):
        result = asyncio.run(
            imports.hydrate_import_archive(
                admin_user.id,
                rom,
                _resolved(_clearing_webstation(rom)),
                save=None,
                save_is_foreign=False,
                state=state,
            )
        )
    assert result.path == "rom-1.zip"
    assert result.state_imported is True
    uploaded_bytes = upload.call_args.args[2]
    with zipfile.ZipFile(io.BytesIO(uploaded_bytes)) as zf:
        assert ".import/state/Game.00.pcsx2" in zf.namelist()


def test_a_defaulted_foreign_save_that_fails_to_read_leaves_the_native_base(
    rom: Rom, admin_user: User
):
    """The launch defaulted to a newer bare .srm whose file is gone, so the
    state import carries the newest archive rather than no save at all."""
    native = _add_save(
        rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1"
    )
    raw = _add_save(rom, admin_user, "Game [b].srm", "mgba", "h2")
    state = _add_state(rom, admin_user, "Game.00.pcsx2", "pcsx2")

    async def read(path: str) -> bytes:
        if path == raw.full_path:
            raise FileNotFoundError(path)
        return path.encode()

    build = MagicMock(wraps=imports.build_import_archive)
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=read),
        ),
        patch("handler.streaming.imports.build_import_archive", build),
        patch(
            "handler.streaming.imports.webstation.upload_archive",
            return_value="rom-1.zip",
        ),
    ):
        result = asyncio.run(
            imports.hydrate_import_archive(
                admin_user.id,
                rom,
                _resolved(_clearing_webstation(rom)),
                save=raw,
                save_is_foreign=True,
                state=state,
                native_fallback=True,
            )
        )
    assert result.path == "rom-1.zip"
    _rom_id, base, members = build.call_args.args
    assert base == (native.file_name, native.full_path.encode())
    assert [m.kind for m in members] == ["state"]


def test_hydrate_import_archive_falls_through_when_the_only_foreign_read_fails(
    rom: Rom, admin_user: User
):
    """A native save plus a foreign state whose bytes are missing on disk:
    there is nothing foreign to carry, so this must not upload a base-only
    import archive. The caller falls back to ordinary save hydration."""
    save = _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    state = _add_state(rom, admin_user, "Game.00.pcsx2", "pcsx2")
    upload = MagicMock(return_value="rom-1.zip")
    with (
        patch(
            "handler.streaming.imports.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("handler.streaming.imports.webstation.upload_archive", upload),
    ):
        result = asyncio.run(
            imports.hydrate_import_archive(
                admin_user.id,
                rom,
                _resolved(_clearing_webstation(rom)),
                save=save,
                save_is_foreign=False,
                state=state,
            )
        )
    assert result == imports.ImportHydration()
    upload.assert_not_called()


def test_hydrate_import_archive_returns_none_when_nothing_is_foreign(
    rom: Rom, admin_user: User
):
    save = _add_save(rom, admin_user, "Game [retroarch a].saves.zip", "retroarch", "h1")
    result = asyncio.run(
        imports.hydrate_import_archive(
            admin_user.id,
            rom,
            _resolved(_clearing_webstation(rom)),
            save=save,
            save_is_foreign=False,
            state=None,
        )
    )
    assert result.path is None
    assert result.state_imported is False


def test_claim_hydrates_the_picked_save(
    client, access_token, rom: Rom, admin_user: User
):
    """The claim carries the pick all the way into the activate body."""
    picked, *_ = _three_archives(rom, admin_user)
    activate = MagicMock(return_value={"url": "/room/x"})
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.filesystem.fs_asset_handler.read_file",
                new=AsyncMock(side_effect=lambda path: path.encode()),
            ),
            patch(
                "handler.streaming.webstation.upload_archive",
                return_value="/config/picked.zip",
            ) as upload,
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            r = _claim(client, access_token, rom.id, save_id=picked.id)
    assert r.status_code == 202
    assert upload.call_args[0][2] == picked.full_path.encode()
    assert activate.call_args.kwargs["archive_path"] == "/config/picked.zip"


def test_claim_hydrates_a_foreign_save_through_the_import_path(
    client, access_token, rom: Rom, admin_user: User
):
    """A foreign save pick must be uploaded through imports.hydrate_import_archive,
    not the native hydrate_saves_to_webstation path."""
    foreign = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    spec = webstation.ImportSpec(
        kinds=frozenset({"save"}),
        state_channel="archive",
        state_slot=0,
    )
    activate = MagicMock(return_value={"url": "/room/x"})
    hydrate_import = AsyncMock(return_value=imports.ImportHydration("rom-1.zip", False))
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.saves.webstation.require_import_spec",
                return_value=spec,
            ),
            patch(
                "endpoints.streaming.webstation.require_import_spec", return_value=spec
            ),
            patch("handler.streaming.imports.hydrate_import_archive", hydrate_import),
            patch("handler.streaming.background.spawn_sync_task"),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            resp = _claim(client, access_token, rom.id, save_id=foreign.id)
    assert resp.status_code == 202
    hydrate_import.assert_called_once()
    call_kwargs = hydrate_import.call_args.kwargs
    assert call_kwargs["save_is_foreign"] is True
    assert call_kwargs["save"].id == foreign.id


def test_claim_hydrates_a_foreign_resume_state_through_the_import_path(
    client, access_token, rom: Rom, admin_user: User
):
    """A foreign resume pick must actually land in the uploaded archive, not
    just be trusted to: this is what proves resume_via_import is only ever
    set once the state import genuinely succeeded."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="archive",
        state_slot=0,
    )
    activate = MagicMock(return_value={"url": "/room/x"})
    upload = MagicMock(return_value="rom-1.zip")
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.states.webstation.require_import_spec",
                return_value=spec,
            ),
            patch(
                "endpoints.streaming.webstation.require_import_spec", return_value=spec
            ),
            patch(
                "handler.streaming.imports.fs_asset_handler.read_file",
                new=AsyncMock(side_effect=lambda path: path.encode()),
            ),
            patch("handler.streaming.imports.webstation.upload_archive", upload),
            patch("handler.streaming.background.spawn_sync_task"),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id, state_id=state.id)
    assert r.status_code == 202
    upload.assert_called_once()
    uploaded_bytes = upload.call_args.args[2]
    with zipfile.ZipFile(io.BytesIO(uploaded_bytes)) as zf:
        assert any(name.startswith(".import/state/") for name in zf.namelist())
    assert [event for event, _ in sent] == ["streaming:launch-ready"]
    assert _launch_ready(sent)["resume"] is True


def test_a_missing_foreign_state_does_not_falsely_claim_resume_via_import(
    client, access_token, rom: Rom, admin_user: User
):
    """The foreign state's bytes are missing on disk, so the import archive
    never actually carries it. the resume must not reach run_launch as
    imported on the strength of the pre-win check alone, and the native save
    hydration path must still get its turn."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="archive",
        state_slot=0,
    )
    native_hydrate = AsyncMock(return_value=None)
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_webstation(rom)):
        with (
            patch(
                "handler.streaming.states.webstation.require_import_spec",
                return_value=spec,
            ),
            patch(
                "endpoints.streaming.webstation.require_import_spec", return_value=spec
            ),
            patch(
                "handler.streaming.imports.fs_asset_handler.read_file",
                new=AsyncMock(side_effect=FileNotFoundError),
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", native_hydrate
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, state_id=state.id)
    assert r.status_code == 202
    run_launch_mock.assert_called_once()
    assert run_launch_mock.call_args.kwargs["resume_import"] == "lost"
    native_hydrate.assert_called_once()


def test_claim_refuses_a_foreign_save_the_won_container_will_not_import(
    client, access_token, rom: Rom, admin_user: User
):
    """The won container's own import-spec decides: a pick it will not take is
    refused and the claim released, never uploaded as a native archive."""
    foreign = _add_save(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    spec = webstation.ImportSpec(
        kinds=frozenset({"save"}),
        state_channel="archive",
        state_slot=0,
    )
    native_hydrate = AsyncMock(return_value=None)
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_webstation(rom)):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec",
                side_effect=[spec, None],
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", native_hydrate
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, save_id=foreign.id)
        assert _session_raw(_clearing_webstation(rom)) is None
    assert r.status_code == 400
    native_hydrate.assert_not_called()
    run_launch_mock.assert_not_called()


def test_claim_asks_for_a_retry_when_the_won_container_did_not_answer(
    client, access_token, rom: Rom, admin_user: User
):
    """A foreign pick the won container couldn't be asked about releases the
    claim and asks for a retry."""
    foreign = _add_save(rom, admin_user, "Game.srm", "mgba", "h1")
    spec = webstation.ImportSpec(
        kinds=frozenset({"save"}), state_channel="push", state_slot=10
    )
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_webstation(rom)):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec",
                side_effect=[spec, webstation.ImportSpecUnavailable],
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, save_id=foreign.id)
        assert _session_raw(_clearing_webstation(rom)) is None
    assert r.status_code == 503
    run_launch_mock.assert_not_called()


def test_claim_refuses_a_foreign_state_the_won_container_will_not_import(
    client, access_token, rom: Rom, admin_user: User
):
    """A foreign state the won container will not take must not fall through to
    the native push, where the emulator would load another emulator's bytes."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="archive",
        state_slot=0,
    )
    push = AsyncMock(return_value=True)
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_webstation(rom)):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec",
                side_effect=[spec, None],
            ),
            patch("handler.streaming.states.push_resume_state", push),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, state_id=state.id)
        assert _session_raw(_clearing_webstation(rom)) is None
    assert r.status_code == 400
    push.assert_not_called()
    run_launch_mock.assert_not_called()


def test_claim_with_an_unrestorable_pick_never_reserves_a_container(
    client, access_token, rom: Rom, admin_user: User
):
    """The pick is validated before the claim, so a bad one fails cleanly
    rather than leaving a container wedged behind a refused launch."""
    loose = _add_save(rom, admin_user, "Game.srm", "retroarch", "h1")
    activate = MagicMock(return_value={"url": "/room/x"})
    with _streaming(_clearing_webstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.saves.webstation.require_import_spec",
                return_value=None,
            ),
            _spawns_nothing(),
        ):
            refused = _claim(client, access_token, rom.id, save_id=loose.id)
            after = _claim(client, access_token, rom.id)
    assert refused.status_code == 400
    activate.assert_called_once()
    assert after.status_code == 202


def test_claim_hydrates_saves_before_launch(client, access_token, rom: Rom):
    """Claiming a session must push stored in-game saves to the container before
    the broker launch (games read saves at boot)."""
    call_order = []
    with _streaming(_container_for(rom)):
        with (
            patch(
                "handler.streaming.commands.launch",
                side_effect=lambda *a, **k: call_order.append("launch"),
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_broker",
                new=AsyncMock(side_effect=lambda *a, **k: call_order.append("saves")),
            ) as hydrate_saves,
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    hydrate_saves.assert_awaited_once()
    assert call_order == ["saves", "launch"]


def test_run_launch_sends_rom_identity_fields(rom: Rom, admin_user: User):
    """The broker needs the ROM's identity triple to answer import-spec and
    to fold a foreign pick's members against the right title."""
    rom.title_id = "SLUS-12345"
    rom.save_target = "SLUS-12345"
    rom.save_target_layout = SaveTargetLayout.FOLDER_EXACT
    activate = MagicMock(return_value={"url": "/room/x"})
    session = {"broker_session_id": "s1", "claimed_at": "t1", "user_id": admin_user.id}
    with (
        patch("handler.streaming.launch.webstation.activate", activate),
        patch("handler.streaming.launch.lifecycle.hold_session_claim", new=AsyncMock()),
        patch(
            "handler.streaming.launch.lifecycle.publish_session_activity",
            new=AsyncMock(),
        ),
        patch("handler.streaming.launch.stamp_launched", new=AsyncMock()),
        patch("handler.streaming.launch.push_to_user", new=AsyncMock()),
        patch("handler.streaming.launch.background.spawn_sync_task"),
        patch(
            "handler.streaming.launch.states.hydrate_states_to_broker", new=AsyncMock()
        ),
    ):
        asyncio.run(
            launch.run_launch(
                container=_resolved(_webstation_for(rom)),
                session_key="k1",
                session=session,
                user=admin_user,
                rom=rom,
                platform=rom.platform_slug,
                rom_name=rom.name or rom.fs_name_no_ext,
                rom_path="rom/path",
                rom_language=None,
                gui_language=None,
                archive_path=None,
                resume_state=None,
                resume_slot=None,
                resume_pushed=False,
                resume_after_launch=False,
                resume_import="none",
                memory_card_synced=False,
                multiplayer=False,
                blank_card_id=None,
            )
        )
    sent_rom = activate.call_args.kwargs["rom"]
    assert sent_rom["title_id"] == "SLUS-12345"
    assert sent_rom["save_target"] == "SLUS-12345"
    assert sent_rom["save_target_layout"] == "folder-exact"


def test_run_launch_pushes_refusals_when_the_broker_refuses_an_import(
    rom: Rom, admin_user: User
):
    """An import refusal must reach the player's tabs as structured refusal
    data, not just a flattened error string."""
    refusal = ImportRefusalSchema(
        reason="shape_mismatch",
        member=".import/save/Game.mcr",
        expected="folder",
        detail=None,
        suggest_emulator=None,
        docs=None,
    )
    activate = MagicMock(side_effect=broker.ImportRefusedError([refusal], 2))
    session = {"broker_session_id": "s1", "claimed_at": "t1", "user_id": admin_user.id}
    pushed = AsyncMock()
    with (
        patch("handler.streaming.launch.webstation.activate", activate),
        patch("handler.streaming.launch.lifecycle.hold_session_claim", new=AsyncMock()),
        patch("handler.streaming.launch.lifecycle.abort_claim", new=AsyncMock()),
        patch("handler.streaming.launch.push_to_user", pushed),
    ):
        asyncio.run(
            launch.run_launch(
                container=_resolved(_webstation_for(rom)),
                session_key="k1",
                session=session,
                user=admin_user,
                rom=rom,
                platform=rom.platform_slug,
                rom_name=rom.name or rom.fs_name_no_ext,
                rom_path="rom/path",
                rom_language=None,
                gui_language=None,
                archive_path=None,
                resume_state=None,
                resume_slot=None,
                resume_pushed=False,
                resume_after_launch=False,
                resume_import="none",
                memory_card_synced=False,
                multiplayer=False,
                blank_card_id=None,
            )
        )
    payload = pushed.call_args.args[2]
    assert payload["refusals"] == [
        {
            "reason": "shape_mismatch",
            "member": ".import/save/Game.mcr",
            "expected": "folder",
            "detail": None,
            "suggest_emulator": None,
            "docs": None,
        }
    ]
    assert payload["refusals_truncated"] == 2
    assert "shape_mismatch" in payload["detail"]


def test_activate_refusal_frees_the_container_for_a_new_claim(
    client, access_token, rom: Rom
):
    """An import refusal at activate time must release the claim, not just
    report it: a second claim on the same container has to succeed too, not
    only see `streaming:launch-failed` and an emptied session record."""
    refusal = ImportRefusalSchema(
        reason="shape_mismatch",
        member=".import/save/Game.mcr",
        expected="folder",
        detail=None,
        suggest_emulator=None,
        docs=None,
    )
    with _streaming(_webstation_for(rom)):
        with (
            patch(
                "handler.streaming.webstation.activate",
                side_effect=broker.ImportRefusedError([refusal], 0),
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", new=AsyncMock()
            ),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id)
        assert [event for event, _ in sent] == ["streaming:launch-failed"]
        assert _session_raw(_webstation_for(rom)) is None

        with (
            patch(
                "handler.streaming.webstation.activate",
                return_value={"url": "/room/x"},
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation", new=AsyncMock()
            ),
            patch("handler.streaming.background.spawn_sync_task"),
        ):
            r2 = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert r2.status_code == 202
    assert _session_raw(_webstation_for(rom)) is not None


def test_run_launch_skips_the_state_push_when_resuming_via_import(
    rom: Rom, admin_user: User
):
    """A foreign state folded into the import archive must not also be
    pushed through the ordinary state-file PUT."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    activate = MagicMock(return_value={"url": "/room/x"})
    session = {"broker_session_id": "s1", "claimed_at": "t1", "user_id": admin_user.id}
    push_resume = AsyncMock()
    with (
        patch("handler.streaming.launch.webstation.activate", activate),
        patch("handler.streaming.launch.lifecycle.hold_session_claim", new=AsyncMock()),
        patch(
            "handler.streaming.launch.lifecycle.publish_session_activity",
            new=AsyncMock(),
        ),
        patch("handler.streaming.launch.stamp_launched", new=AsyncMock()),
        patch("handler.streaming.launch.push_to_user", new=AsyncMock()),
        patch("handler.streaming.launch.background.spawn_sync_task"),
        patch(
            "handler.streaming.launch.states.hydrate_states_to_broker", new=AsyncMock()
        ),
        patch("handler.streaming.launch.states.push_resume_state", push_resume),
    ):
        asyncio.run(
            launch.run_launch(
                container=_resolved(_webstation_for(rom)),
                session_key="k1",
                session=session,
                user=admin_user,
                rom=rom,
                platform=rom.platform_slug,
                rom_name=rom.name or rom.fs_name_no_ext,
                rom_path="rom/path",
                rom_language=None,
                gui_language=None,
                archive_path="rom-1.zip",
                resume_state=state,
                resume_slot=0,
                resume_pushed=False,
                resume_after_launch=True,
                resume_import="imported",
                memory_card_synced=False,
                multiplayer=False,
                blank_card_id=None,
            )
        )
    push_resume.assert_not_called()


def test_run_launch_sends_no_resume_slot_when_the_import_was_lost(
    rom: Rom, admin_user: User
):
    """A pick that never made it into its import archive must not have the
    broker load that slot anyway, from whatever the archive does carry."""
    state = _add_state(rom, admin_user, "Game.00.dolphin", "dolphin")
    activate = MagicMock(return_value={"url": "/room/x"})
    session = {"broker_session_id": "s1", "claimed_at": "t1", "user_id": admin_user.id}
    push_resume = AsyncMock()
    with (
        patch("handler.streaming.launch.webstation.activate", activate),
        patch("handler.streaming.launch.lifecycle.hold_session_claim", new=AsyncMock()),
        patch(
            "handler.streaming.launch.lifecycle.publish_session_activity",
            new=AsyncMock(),
        ),
        patch("handler.streaming.launch.stamp_launched", new=AsyncMock()),
        patch("handler.streaming.launch.background.spawn_sync_task"),
        patch(
            "handler.streaming.launch.states.hydrate_states_to_broker", new=AsyncMock()
        ),
        patch("handler.streaming.launch.states.push_resume_state", push_resume),
    ):
        with _pushes() as sent:
            asyncio.run(
                launch.run_launch(
                    container=_resolved(_webstation_for(rom)),
                    session_key="k1",
                    session=session,
                    user=admin_user,
                    rom=rom,
                    platform=rom.platform_slug,
                    rom_name=rom.name or rom.fs_name_no_ext,
                    rom_path="rom/path",
                    rom_language=None,
                    gui_language=None,
                    archive_path="rom-1.zip",
                    resume_state=state,
                    resume_slot=0,
                    resume_pushed=False,
                    resume_after_launch=True,
                    resume_import="lost",
                    memory_card_synced=False,
                    multiplayer=False,
                    blank_card_id=None,
                )
            )
    assert activate.call_args.kwargs["resume_slot"] is None
    push_resume.assert_not_called()
    assert _launch_ready(sent)["resume"] is False


def test_release_spawns_saves_pull(client, access_token, rom: Rom):
    """Releasing a session must schedule a background pull of in-game saves."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.pull_saves_to_library",
                new_callable=AsyncMock,
            ) as pull,
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
            spawn.assert_called_once()
            asyncio.run(spawn.call_args[0][0])
    assert r.status_code == 200
    pull.assert_awaited_once()
    assert pull.await_args_list[0].args[1] == rom.id


def test_a_claim_behind_an_exit_waits_for_that_exits_saves(
    client, access_token, admin_user: User, rom: Rom
):
    """Runs both ends for real: nothing else ties the key an exit marks to the
    one the next claim waits on."""
    # Equal ids would let a claim that swaps them find the exit's key anyway.
    if rom.id == admin_user.id:
        rom = _rom_on("distinct_id")
    order: list[str] = []
    real_wait = saves.wait_for_save_pull

    async def slow_pull(*args, **kwargs) -> bool:
        await asyncio.sleep(saves._SAVE_PULL_POLL_SECONDS * 2)
        order.append("filed")
        return True

    async def hydrate(*args, **kwargs) -> bool:
        order.append("hydrate")
        return True

    async def wait_while_it_files(user_id: int, rom_id: int) -> bool:
        filing = asyncio.ensure_future(spawn.call_args[0][0])
        done = await real_wait(user_id, rom_id, budget=5)
        order.append("waited" if done else "gave up")
        await filing
        return done

    with (
        _streaming(_container_for(rom)),
        patch("handler.streaming.saves.pull_saves_to_library", new=slow_pull),
    ):
        _claim_ok(client, access_token, rom.id)
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
        with (
            patch(
                "handler.streaming.saves.wait_for_save_pull", new=wait_while_it_files
            ),
            patch("handler.streaming.saves.hydrate_saves_to_broker", new=hydrate),
        ):
            r = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 202
    assert order == ["filed", "waited", "hydrate"]


async def _save_pull_pending(user_id: int, rom_id: int) -> bool:
    """Whether a claim would wait on a save pull, read the way the claim reads it."""
    return not await saves.wait_for_save_pull(user_id, rom_id, budget=0)


def test_a_release_marks_its_save_pull_before_stopping_the_emulator(
    client, access_token, admin_user: User, rom: Rom
):
    """On a pool the player's next claim lands on a free sibling while this
    container drains, so the pull has to be pending before the slow part."""
    head, tail = _pool_member(rom, 0), _pool_member(rom, 1)
    at_stop: list[tuple[bool, bool]] = []

    async def quiesce(container, session, *, save=True):
        sibling_free = await session_store.get_live_session(_key_of(tail)) is None
        at_stop.append((sibling_free, await _save_pull_pending(admin_user.id, rom.id)))
        return commands.StopOutcome()

    with _streaming(head, tail):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("handler.streaming.lifecycle.quiesce_container", new=quiesce),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
        spawn.call_args[0][0].close()
    assert r.status_code == 200
    assert at_stop == [(True, True)]


def test_an_abandoned_teardown_marks_its_save_pull_before_stopping_the_emulator(
    client, access_token, admin_user: User, rom: Rom
):
    container = _container_for(rom)
    at_stop: list[bool] = []

    async def quiesce(container, session, *, save=True):
        at_stop.append(await _save_pull_pending(admin_user.id, rom.id))
        return commands.StopOutcome()

    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        session = json.loads(_session_raw(container))
        with (
            patch("handler.streaming.lifecycle.quiesce_container", new=quiesce),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            torn = asyncio.run(
                lifecycle.teardown_abandoned_session(
                    _resolved(container),
                    _key_of(container),
                    session,
                    claimed_by=admin_user.id,
                )
            )
        spawn.call_args[0][0].close()
    assert torn is True
    assert at_stop == [True]


def test_a_release_that_fails_before_its_pull_leaves_nothing_pending(
    client, access_token, admin_user: User, rom: Rom
):
    """Only a pull clears the mark, so a teardown that never gets to one has to,
    or the player's next claim sits out the whole wait for nothing."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.lifecycle.quiesce_container",
                new=AsyncMock(side_effect=RuntimeError("broker gone")),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    spawn.assert_not_called()
    assert asyncio.run(_save_pull_pending(admin_user.id, rom.id)) is False


def test_an_abandoned_teardown_that_fails_before_its_pull_leaves_nothing_pending(
    client, access_token, admin_user: User, rom: Rom
):
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        session = json.loads(_session_raw(container))
        with (
            patch(
                "handler.streaming.lifecycle.quiesce_container",
                new=AsyncMock(side_effect=RuntimeError("broker gone")),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            asyncio.run(
                lifecycle.teardown_abandoned_session(
                    _resolved(container),
                    _key_of(container),
                    session,
                    claimed_by=admin_user.id,
                )
            )
    spawn.assert_not_called()
    assert asyncio.run(_save_pull_pending(admin_user.id, rom.id)) is False


def _run_exit_pulls(spawn: MagicMock) -> None:
    """Run the save pulls a teardown spawned, and drop whatever else it did."""
    for spawned in (c.args[0] for c in spawn.call_args_list):
        if spawned.cr_code.co_name == "pull_exit_saves":
            asyncio.run(spawned)
        else:
            spawned.close()


def test_a_webstation_exit_that_changed_no_saves_lets_the_next_claim_straight_through(
    client, access_token, rom: Rom, monkeypatch
):
    """A webstation exit answers once the save dump is written, so its first
    "nothing new" is final and retrying it only holds the next claim."""
    # Long enough that a single retry outlasts the claim's wait below.
    monkeypatch.setattr(broker, "PULL_RETRY_DELAY", 1.0)
    waited: list[bool] = []
    real_wait = saves.wait_for_save_pull

    async def wait_while_it_files(user_id: int, rom_id: int) -> bool:
        filing = asyncio.ensure_future(pull)
        waited.append(await real_wait(user_id, rom_id, budget=0.5))
        filing.cancel()
        return waited[-1]

    with (
        _streaming(_webstation_for(rom)),
        patch("handler.streaming.saves.fetch_save_archive", return_value=None),
    ):
        _claim_webstation_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.webstation.exit_session",
                return_value={"state_saved": False, "state_slot": None},
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
        (pull,) = (
            c.args[0]
            for c in spawn.call_args_list
            if c.args[0].cr_code.co_name == "pull_exit_saves"
        )
        with patch(
            "handler.streaming.saves.wait_for_save_pull", new=wait_while_it_files
        ):
            r = _claim_webstation_ok(client, access_token, rom.id)
    assert r.status_code == 202
    assert waited == [True]


def test_a_webstation_exit_that_never_answered_keeps_asking(
    client, access_token, rom: Rom
):
    """An exit that timed out or failed may still be writing the dump."""
    with _streaming(_webstation_for(rom)):
        _claim_webstation_ok(client, access_token, rom.id)
        with (
            patch("handler.streaming.webstation.exit_session", return_value=None),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == broker.PULL_ATTEMPTS


@pytest.mark.parametrize(
    ("exit_report", "wait", "attempts"),
    [
        (None, True, broker.PULL_ATTEMPTS),
        ({"state_saved": True, "state_slot": 10}, False, 1),
        ({"state_saved": False, "state_slot": None}, True, 1),
    ],
)
def test_a_webstation_save_and_exit_takes_one_answer_only_once_its_exit_answers(
    client,
    access_token,
    rom: Rom,
    exit_report: dict[str, Any] | None,
    wait: bool,
    attempts: int,
):
    """This exit always blocks until the dump is written, whatever wait says,
    but one that timed out or failed may still be writing it."""
    with _streaming(_webstation_for(rom)):
        _claim_webstation_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.webstation.exit_session", return_value=exit_report
            ),
            patch(
                "handler.streaming.states.pull_state_to_library",
                new=AsyncMock(return_value=True),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": wait},
                headers=_auth(access_token),
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == attempts


def test_a_release_keeps_asking_while_the_emulator_flushes(
    client, access_token, rom: Rom
):
    """A per-emulator broker acks the stop before the emulator has flushed its
    saves, so an early "nothing new" is not the answer yet."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == broker.PULL_ATTEMPTS


def test_an_abandoned_teardown_keeps_asking_while_the_emulator_flushes(
    client, access_token, admin_user: User, rom: Rom
):
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, session_store._STREAMING_SESSION_STALE_SECONDS + 60)
        session = json.loads(_session_raw(container))
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            asyncio.run(
                lifecycle.teardown_abandoned_session(
                    _resolved(container),
                    _key_of(container),
                    session,
                    claimed_by=admin_user.id,
                )
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == broker.PULL_ATTEMPTS


def test_a_force_release_keeps_asking_while_the_emulator_flushes(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            _stub_stop(),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.delete("/api/streaming/sessions", headers=_auth(access_token))
            _run_exit_pulls(spawn)
    assert fetch.call_count == broker.PULL_ATTEMPTS


def _broker_saves(body: dict[str, Any]):
    """A broker whose save-and-exit answers with `body`, and nothing else."""
    return lambda _container, path, *args, **kwargs: (
        body if path == "/save-and-exit" else None
    )


@pytest.mark.parametrize(
    ("saved", "attempts"), [(True, 1), (False, broker.PULL_ATTEMPTS)]
)
def test_a_blocking_save_and_exit_takes_one_answer_only_once_the_broker_confirms(
    client, access_token, rom: Rom, saved: bool, attempts: int
):
    """A save-and-exit that timed out or failed may still be killing the
    emulator, so only a confirmed one has finished writing."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.broker.request_safe",
                side_effect=_broker_saves({"saved": saved, "slot": 10}),
            ),
            patch(
                "handler.streaming.states.pull_state_to_library",
                new=AsyncMock(return_value=True),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == attempts


def test_a_background_save_and_exit_keeps_asking_while_the_emulator_writes(
    client, access_token, rom: Rom
):
    """With wait=false the broker is still saving when the pull starts, so an
    early "nothing new" is not the answer yet, even from a save it confirmed."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.broker.request_safe",
                side_effect=_broker_saves({"saved": True, "slot": 10}),
            ),
            patch(
                "handler.streaming.states.pull_state_to_library",
                new=AsyncMock(return_value=True),
            ),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch(
                "handler.streaming.saves.fetch_save_archive", return_value=None
            ) as fetch,
        ):
            client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": False},
                headers=_auth(access_token),
            )
            _run_exit_pulls(spawn)
    assert fetch.call_count == broker.PULL_ATTEMPTS


def test_save_and_exit_marks_the_save_pull_before_giving_up_the_key(
    client, access_token, admin_user: User, rom: Rom
):
    """With no state to wait on, the key is deleted outright, so a claim can win
    it the moment it goes and has to find the pull already pending."""
    key = saves._save_pull_redis_key(admin_user.id, rom.id)
    pending_at_release: list[int] = []
    real_release = release_own_session

    async def release_after_looking(*args, **kwargs):
        pending_at_release.append(await async_cache.exists(key))
        return await real_release(*args, **kwargs)

    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(False, 10, False),
            ),
            patch("handler.streaming.background.spawn_sync_task"),
            patch.object(streaming, "release_own_session", release_after_looking),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 0, "wait": True},
                headers=_auth(access_token),
            )
        asyncio.run(async_cache.delete(key))
    assert r.status_code == 200
    assert pending_at_release == [1]


def test_a_claim_waits_for_a_running_save_pull():
    async def scenario() -> bool:
        mark = await saves.mark_save_pull_pending(1, 2)
        waiter = asyncio.create_task(saves.wait_for_save_pull(1, 2, budget=5))
        await asyncio.sleep(saves._SAVE_PULL_POLL_SECONDS * 2)
        assert not waiter.done()
        await saves.clear_save_pull_pending(mark)
        return await waiter

    assert asyncio.run(scenario()) is True


def test_a_wedged_save_pull_does_not_hang_the_claim():
    """A claim is an interactive request: a pull that never finishes costs the
    player the previous archive, not a claim that never answers."""

    async def scenario() -> bool:
        mark = await saves.mark_save_pull_pending(1, 2)
        try:
            return await saves.wait_for_save_pull(1, 2, budget=0.1)
        finally:
            await saves.clear_save_pull_pending(mark)

    assert asyncio.run(scenario()) is False


def test_a_claim_with_nothing_pending_hydrates_straight_away():
    assert asyncio.run(saves.wait_for_save_pull(1, 2, budget=5)) is True


def test_an_earlier_pull_finishing_leaves_a_later_exits_mark(
    admin_user: User, rom: Rom
):
    """A pull can outlast a claim's wait, so the player can play and exit again
    while it runs, and its finishing must not let a claim past the later pull."""
    entry = _container_for(rom)
    container = _resolved(entry)
    session = {"user_id": admin_user.id, "rom_id": rom.id}

    async def scenario() -> tuple[bool, bool]:
        with (
            _streaming(entry),
            patch("handler.streaming.background.spawn_sync_task") as spawn,
            patch("handler.streaming.saves.pull_saves_to_library", new=AsyncMock()),
        ):
            for _ in range(2):
                mark = await lifecycle.mark_exit_saves_pending(container, session)
                await lifecycle.collect_exit_saves(
                    container, session, mark, settled=False
                )
            first, second = (c.args[0] for c in spawn.call_args_list)
            await first
            behind_second = await _save_pull_pending(admin_user.id, rom.id)
            await second
            return behind_second, await _save_pull_pending(admin_user.id, rom.id)

    assert asyncio.run(scenario()) == (True, False)


def test_an_exit_save_pull_runs_on_the_streaming_worker(
    admin_user: User, rom: Rom, exit_pull_queue: MagicMock
):
    """A web restart would otherwise cut a pull short and park the next claim."""
    container = _resolved(_container_for(rom))
    session = {
        "user_id": admin_user.id,
        "rom_id": rom.id,
        "broker_session_id": "b1",
        "disc_file_id": 42,
        "disc_swaps": [{"file_id": 42, "at": "2026-10-07T12:00:00+00:00"}],
    }
    exit_pull_queue.enqueue.side_effect = None

    async def scenario() -> saves.SavePullMark | None:
        mark = await lifecycle.mark_exit_saves_pending(container, session)
        await lifecycle.collect_exit_saves(container, session, mark, settled=True)
        return mark

    mark = asyncio.run(scenario())

    assert mark is not None
    (func,), kwargs = exit_pull_queue.enqueue.call_args
    assert func is lifecycle.pull_exit_saves
    assert kwargs["kwargs"] == {
        "user_id": admin_user.id,
        "rom_id": rom.id,
        "token": mark.token,
        "container_key": container.key,
        "platform": container.platform,
        "broker_session": "b1",
        "settled": True,
        "disc_file_id": 42,
        "disc_swaps": [
            session_store.DiscSwap(42, datetime(2026, 10, 7, 12, tzinfo=timezone.utc))
        ],
    }
    assert kwargs["job_timeout"] == saves.SAVE_PULL_TTL_SECONDS


def test_a_queued_exit_save_pull_hands_on_the_disc(admin_user: User, rom: Rom):
    session = {"user_id": admin_user.id, "rom_id": rom.id}

    async def scenario() -> AsyncMock:
        container = _resolved(_container_for(rom))
        mark = await lifecycle.mark_exit_saves_pending(container, session)
        assert mark is not None
        with (
            _streaming(_container_for(rom)),
            patch(
                "handler.streaming.saves.pull_saves_to_library", new=AsyncMock()
            ) as pull,
        ):
            await lifecycle.pull_exit_saves(
                user_id=mark.user_id,
                rom_id=mark.rom_id,
                token=mark.token,
                container_key=container.key,
                platform=container.platform,
                broker_session=None,
                settled=True,
                disc_file_id=42,
                disc_swaps=[swap],
            )
        return pull

    swap = session_store.DiscSwap(42, datetime(2026, 10, 7, 12, tzinfo=timezone.utc))
    pull = asyncio.run(scenario())
    assert pull.call_args.kwargs["disc_file_id"] == 42
    assert pull.call_args.kwargs["disc_swaps"] == [swap]


def test_a_pull_that_cannot_be_queued_lets_the_next_claim_through(
    admin_user: User, rom: Rom, exit_pull_queue: MagicMock
):
    container = _resolved(_container_for(rom))
    session = {"user_id": admin_user.id, "rom_id": rom.id}
    exit_pull_queue.enqueue.side_effect = ConnectionError("redis went away")

    async def scenario() -> bool:
        mark = await lifecycle.mark_exit_saves_pending(container, session)
        await lifecycle.collect_exit_saves(container, session, mark, settled=False)
        return await _save_pull_pending(admin_user.id, rom.id)

    assert asyncio.run(scenario()) is False


def test_a_queued_pull_for_a_container_no_longer_configured_clears_its_mark(
    admin_user: User, rom: Rom
):
    session = {"user_id": admin_user.id, "rom_id": rom.id}

    async def scenario() -> tuple[bool, AsyncMock]:
        container = _resolved(_container_for(rom))
        mark = await lifecycle.mark_exit_saves_pending(container, session)
        assert mark is not None
        with (
            _streaming(),
            patch(
                "handler.streaming.saves.pull_saves_to_library", new=AsyncMock()
            ) as pull,
        ):
            await lifecycle.pull_exit_saves(
                user_id=mark.user_id,
                rom_id=mark.rom_id,
                token=mark.token,
                container_key=container.key,
                platform=container.platform,
                broker_session=None,
                settled=False,
            )
        return await _save_pull_pending(admin_user.id, rom.id), pull

    pending, pull = asyncio.run(scenario())
    assert pending is False
    pull.assert_not_awaited()


# ── Resume-from-state ─────────────────────────────────────────────────────────


def test_slot_from_state_filename():
    assert states.slot_from_state_filename("pcsx2", "SLUS (A1B2).3.p2s") == 3
    assert states.slot_from_state_filename("pcsx2", "SLUS (A1B2).10.p2s") == 10
    assert states.slot_from_state_filename("dolphin", "GALE01.s02") == 2
    assert states.slot_from_state_filename("pcsx2", "Game.p2s") is None
    assert states.slot_from_state_filename("dolphin", "GALE01.gci") is None
    assert states.slot_from_state_filename("pcsx2", "Game.0.p2s") is None
    assert states.slot_from_state_filename("xemu", "MechAssault (USA).x03") == 3
    assert states.slot_from_state_filename("xemu", "MechAssault (USA).x10") == 10
    assert states.slot_from_state_filename("xemu", "MechAssault (USA).qcow2") is None
    # RetroArch leaves the number off its default slot, and unlike the others
    # it really does work in slot 0, so an empty token resolves rather than
    # reading as an unrecognizable name.
    assert states.slot_from_state_filename("retroarch", "Game.state") == 0
    assert states.slot_from_state_filename("retroarch", "Game.state7") == 7
    assert states.slot_from_state_filename("retroarch", "Game.srm") is None


def test_stamped_state_filename_round_trips_for_xemu():
    when = datetime(2026, 7, 21, 4, 56, 45, 123456, tzinfo=timezone.utc)
    stamped = states.stamped_state_filename("xemu", "MechAssault.x03", when)
    assert re.fullmatch(r"MechAssault\.\d{8}-\d{12}\.x03", stamped)
    assert states.container_state_filename(stamped) == "MechAssault.x03"


def test_stamped_state_filename_round_trips_for_retroarch():
    """The stamp goes before the slot token even when the token is empty, so
    every capture is its own file and the container name is still recoverable."""
    when = datetime(2026, 7, 21, 4, 56, 45, 123456, tzinfo=timezone.utc)
    stamped = states.stamped_state_filename("retroarch", "Super Mario.state", when)
    assert re.fullmatch(r"Super Mario\.\d{8}-\d{12}\.state", stamped)
    assert states.container_state_filename(stamped) == "Super Mario.state"


def test_exit_state_filenames_resolve_to_the_working_slot():
    """DuckStation and RPCS3 write one state per game, as they exit, with no
    slot in its name, so the working slot is the only one a pick can mean."""
    assert states.slot_from_state_filename("duckstation", "SLUS-00594_resume.sav") == 0
    assert states.slot_from_state_filename("duckstation", "SLUS-00594.mcd") is None
    assert states.slot_from_state_filename("rpcs3", "BLUS30443_1.SAVESTAT") == 0
    assert states.slot_from_state_filename("rpcs3", "BLUS30443_1.SAVESTAT.zst") == 0
    assert states.slot_from_state_filename("rpcs3", "BLUS30443_1.SAVESTAT.gz") == 0
    assert states.slot_from_state_filename("rpcs3", "PARAM.SFO") is None


@pytest.mark.parametrize(
    ("emulator", "name", "shape"),
    [
        (
            "duckstation",
            "SLUS-00594_resume.sav",
            r"SLUS-00594_resume\.\d{8}-\d{12}\.sav",
        ),
        (
            "rpcs3",
            "BLUS30443_1.SAVESTAT.zst",
            r"BLUS30443_1\.\d{8}-\d{12}\.SAVESTAT\.zst",
        ),
    ],
)
def test_stamped_exit_state_filename_round_trips(emulator, name, shape):
    """Every exit is its own library entry, and the stamped name still resolves
    a slot: otherwise the entries the stamp creates could never be picked."""
    when = datetime(2026, 7, 21, 4, 56, 45, 123456, tzinfo=timezone.utc)
    stamped = states.stamped_state_filename(emulator, name, when)
    assert re.fullmatch(shape, stamped)
    assert states.container_state_filename(stamped) == name
    assert states.slot_from_state_filename(emulator, stamped) == 0


def test_stamped_auto_state_filename_keeps_its_container_name():
    """Each auto capture gets its own name and resumes from the working slot."""
    first = datetime(2026, 7, 21, 4, 56, 45, 123456, tzinfo=timezone.utc)
    second = datetime(2026, 7, 21, 4, 56, 45, 123457, tzinfo=timezone.utc)
    stamped = states.stamped_state_filename("retroarch", "Game.state.auto", first)
    assert re.fullmatch(r"Game\.\d{8}-\d{12}\.state\.auto", stamped)
    assert stamped != states.stamped_state_filename(
        "retroarch", "Game.state.auto", second
    )
    assert states.container_state_filename(stamped) == "Game.state.auto"
    assert states.slot_from_state_filename("retroarch", stamped) == 0


class _ResumeClaim(NamedTuple):
    response: httpx2.Response
    ready: dict[str, Any]
    push: MagicMock
    call_broker: MagicMock
    hydrate: MagicMock


def _resume_claim(client, token, rom, state_id, push_ok=True) -> _ResumeClaim:
    """Claim with a resume state and full launch-path mocks.

    `ready` is the launch-ready push, which is where the resume outcome lands
    now that the claim answers before the launch runs.
    """
    container = {**_container_for(rom), "label": "PCSX2"}
    with _streaming(container):
        with (
            patch("handler.streaming.commands.launch") as call_broker,
            patch(
                "handler.streaming.states.push_state_file", return_value=push_ok
            ) as push,
            patch(
                "handler.filesystem.fs_asset_handler.read_file",
                new=AsyncMock(return_value=b"state-bytes"),
            ),
            _spawns_nothing(),
            patch(
                "handler.streaming.states.hydrate_states_to_broker", new=MagicMock()
            ) as hydrate,
        ):
            with _pushes() as sent:
                r = _claim(client, token, rom.id, state_id=state_id)
    return _ResumeClaim(r, _launch_ready(sent), push, call_broker, hydrate)


def test_claim_with_own_state_pushes_file_and_slot(
    client, access_token, rom: Rom, admin_user: User
):
    """A picked state is pushed before launch and its slot rides the launch
    call; hydration must skip that filename so it cannot be overwritten."""
    state = _add_state(rom, admin_user, "Game.03.p2s", "pcsx2")
    r, ready, push, call_broker, hydrate = _resume_claim(
        client, access_token, rom, state.id
    )
    assert r.status_code == 202
    assert ready["resume"] is True
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.03.p2s"
    assert push.call_args[0][2] == b"state-bytes"
    assert call_broker.call_args[0][3] == 3
    assert hydrate.call_args.kwargs["resume_pushed"] is True


def test_claim_with_other_users_public_state_allowed(
    client, access_token, rom: Rom, viewer_user: User
):
    """Resuming from another user's shared state is the sharing feature."""
    state = _add_state(rom, viewer_user, "Game.02.p2s", "pcsx2", is_public=True)
    r, ready, push, call_broker, _ = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 202
    assert ready["resume"] is True
    assert call_broker.call_args[0][3] == 2


def test_claim_with_other_users_private_state_404(
    client, access_token, rom: Rom, viewer_user: User
):
    """Another user's private state is invisible - same as nonexistent."""
    state = _add_state(rom, viewer_user, "Game.02.p2s", "pcsx2")
    r = _resume_claim(client, access_token, rom, state.id).response
    assert r.status_code == 404
    # The rejected pick must not have claimed the container.
    with _streaming(_container_for(rom)):
        assert _claim_ok(client, access_token, rom.id).status_code == 202


def test_claim_with_wrong_emulator_state_400(
    client, access_token, rom: Rom, admin_user: User
):
    state = _add_state(rom, admin_user, "Game.state", "retroarch")
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=None
    ):
        r = _resume_claim(client, access_token, rom, state.id).response
    assert r.status_code == 400


def test_claim_with_unparseable_slot_400(
    client, access_token, rom: Rom, admin_user: User
):
    state = _add_state(rom, admin_user, "Game.p2s", "pcsx2")
    with patch(
        "handler.streaming.states.webstation.require_import_spec", return_value=None
    ):
        r = _resume_claim(client, access_token, rom, state.id).response
    assert r.status_code == 400


def test_claim_failed_push_launches_fresh(
    client, access_token, rom: Rom, admin_user: User
):
    """A push failure must not block the session: launch without load_slot
    and report resume=false so the player can tell the user."""
    state = _add_state(rom, admin_user, "Game.03.p2s", "pcsx2")
    r, ready, _, call_broker, hydrate = _resume_claim(
        client, access_token, rom, state.id, push_ok=False
    )
    assert r.status_code == 202
    assert ready["resume"] is False
    assert call_broker.call_args[0][3] is None
    assert hydrate.call_args.kwargs["resume_pushed"] is False


def test_claim_without_state_reports_no_resume(client, access_token, rom: Rom):
    with _streaming(_container_for(rom)):
        with _pushes() as sent:
            r = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 202
    assert _launch_ready(sent)["resume"] is None


# ── Webstation state sync ─────────────────────────────────────────────────────


def _webstation_for(rom: Rom) -> dict[str, Any]:
    """The container a claim for this ROM's platform lands on, webstation side."""
    return {**_container_for(rom), "protocol": "webstation", "label": "PCSX2"}


def test_state_transfers_reach_the_webstation_broker_under_its_subfolder(rom: Rom):
    """This broker answers behind a subfolder, so an unprefixed path would land
    on the room's web server rather than on the broker."""
    container = _webstation_for(rom)
    resp = MagicMock()
    inner = resp.__enter__.return_value
    inner.headers = {"X-State-Filename": "Game.03.p2s"}

    with patch(
        "handler.streaming.broker.urllib.request.urlopen", return_value=resp
    ) as urlopen:
        inner.read.side_effect = _reads(b"state-bytes")
        states.fetch_state_file(_resolved(container), 3)
        inner.read.side_effect = _reads(_PNG)
        states.fetch_state_screenshot(_resolved(container), 3)
        inner.read.side_effect = _reads(b'{"status": "ok"}')
        states.push_state_file(_resolved(container), "Game.03.p2s", b"bytes")

    root = "http://192.168.1.10:8000/streaming/api/session"
    assert [call.args[0].full_url for call in urlopen.call_args_list] == [
        f"{root}/state-file?slot=3",
        f"{root}/state-screenshot?slot=3",
        f"{root}/state-file?filename=Game.03.p2s",
    ]


def _state_file_response(headers: dict[str, str], body: bytes):
    """A urlopen stand-in answering a state-file request."""
    resp = MagicMock()
    inner = resp.__enter__.return_value
    inner.headers = headers
    inner.read.side_effect = _reads(body)
    return resp


def test_a_pulled_state_names_its_core(rom: Rom):
    resp = _state_file_response(
        {"X-State-Filename": "Game.state", "X-State-Core": "bsnes"}, b"bytes"
    )
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        pulled = states.fetch_state_file(_resolved(_webstation_for(rom)), 0)
    assert pulled == states.PulledState("Game.state", b"bytes", "bsnes")


def test_a_pulled_state_names_its_cores_folder(rom: Rom):
    resp = _state_file_response(
        {
            "X-State-Filename": "Game.state",
            "X-State-Core": "melondsds",
            "X-State-Library": "melonDS DS",
        },
        b"bytes",
    )
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        pulled = states.fetch_state_file(_resolved(_webstation_for(rom)), 0)
    assert pulled == states.PulledState(
        "Game.state", b"bytes", "melondsds", "melonDS DS"
    )


def test_a_pulled_state_from_an_older_broker_has_no_core(rom: Rom):
    resp = _state_file_response({"X-State-Filename": "Game.state"}, b"bytes")
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        pulled = states.fetch_state_file(_resolved(_webstation_for(rom)), 0)
    assert pulled is not None and pulled.core is None


def test_a_pushed_state_names_its_core(rom: Rom):
    container = _resolved(_webstation_for(rom))
    # One response each: a drained body answers EOF to the second call.
    acks = [_state_file_response({}, b'{"status": "ok"}') for _ in range(2)]
    with patch(
        "handler.streaming.broker.urllib.request.urlopen", side_effect=acks
    ) as urlopen:
        assert states.push_state_file(container, "Game.state", b"x", "bsnes")
        states.push_state_file(container, "Game.state", b"x")
    with_core, without = (c.args[0] for c in urlopen.call_args_list)
    assert with_core.get_header("X-state-core") == "bsnes"
    assert without.get_header("X-state-core") is None


def test_a_pulled_state_is_stored_with_its_core(rom: Rom, admin_user: User):
    scanned = _state_for(rom, admin_user, "Game.state", "retroarch")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.state", b"state-bytes", "bsnes"),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(
                admin_user.id, rom.id, _snes("retroarch:bsnes"), 0
            )
        )
    assert ok is True
    stored = states.user_states_for_emulator(admin_user.id, rom.id, "retroarch")
    assert [s.core for s in stored] == ["bsnes"]


def test_a_pulled_state_is_filed_under_its_cores_folder(rom: Rom, admin_user: User):
    store = AsyncMock()
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState(
                "Game.state", b"state-bytes", "melondsds", "melonDS DS"
            ),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch("handler.streaming.states.store_state_asset", store),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(
                admin_user.id, rom.id, _snes("retroarch:melondsds"), 0
            )
        )
    assert ok is True
    kwargs = store.call_args.kwargs
    assert (kwargs["core"], kwargs["library_name"]) == ("melondsds", "melonDS DS")


_CORES_REPLY = {"platform": "snes", "default": "snes9x", "cores": []}


def test_default_core_asks_the_broker_cores_route():
    with patch(
        "handler.streaming.broker.request", return_value=_CORES_REPLY
    ) as request:
        assert webstation.default_core(_snes("retroarch")) == "snes9x"
    assert request.call_args.args[1] == "/streaming/api/retroarch/cores?platform=snes"


def test_default_core_answers_from_cache_within_the_ttl():
    with patch(
        "handler.streaming.broker.request", return_value=_CORES_REPLY
    ) as request:
        webstation.default_core(_snes("retroarch"))
        webstation.default_core(_snes("retroarch"))
    assert request.call_count == 1


def test_default_core_asks_again_once_a_404_expires():
    """An upgraded broker gains the route, so an old one's 404 must not outlive
    the TTL."""
    with (
        patch("handler.streaming.webstation._CORES_TTL", 0.0),
        patch(
            "handler.streaming.broker.request", side_effect=_http_error(404)
        ) as request,
    ):
        assert webstation.default_core(_snes("retroarch")) is None
        webstation.default_core(_snes("retroarch"))
    assert request.call_count == 2


def test_default_core_is_not_asked_outside_retroarch():
    with patch("handler.streaming.broker.request") as request:
        assert webstation.default_core(_resolved(_webstation())) is None
    request.assert_not_called()


def test_state_core_matches_its_own_core_and_unrecorded_default_states():
    assert states.StateCore("bsnes", False).matches("bsnes")
    assert not states.StateCore("bsnes", False).matches(None)
    assert not states.StateCore("bsnes", False).matches("snes9x")
    assert states.StateCore("snes9x", True).matches(None)


def test_state_core_takes_the_core_activate_booted():
    """Once the game is up, the reply says what runs; no second request."""
    with patch("handler.streaming.webstation.default_core") as default_core:
        booted = states.state_core_for(
            _snes("retroarch:bsnes"), {"core": "bsnes", "core_tier": "untested"}
        )
        default = states.state_core_for(
            _snes("retroarch"), {"core": "snes9x", "core_tier": "default"}
        )
    assert booted == states.StateCore("bsnes", default_matches=False)
    assert default == states.StateCore("snes9x", default_matches=True)
    default_core.assert_not_called()


def test_state_core_asks_for_the_default_before_launch():
    with patch("handler.streaming.webstation.default_core", return_value="snes9x"):
        configured = states.state_core_for(_snes("retroarch:bsnes"))
        default = states.state_core_for(_snes("retroarch"))
    assert configured == states.StateCore("bsnes", default_matches=False)
    assert default == states.StateCore("snes9x", default_matches=True)


def test_state_core_is_unknown_when_the_broker_cannot_say():
    """An older broker has no cores route; filtering nothing is what RomM did
    before it knew about cores."""
    with patch("handler.streaming.webstation.default_core", return_value=None):
        assert states.state_core_for(_snes("retroarch")) is None


def test_a_configured_core_still_filters_when_the_default_is_unknown():
    """A NULL row is the default's, and the default is not known to be this
    core, so it stays hidden rather than risk a quick-load of the wrong file."""
    with patch("handler.streaming.webstation.default_core", return_value=None):
        core = states.state_core_for(_snes("retroarch:bsnes"))
    assert core == states.StateCore("bsnes", default_matches=False)


def test_state_core_takes_the_folder_activate_names():
    core = states.state_core_for(
        _snes("retroarch:snes9x2010"),
        {"core": "snes9x2010", "core_tier": "untested", "library_name": "Snes9x 2010"},
    )
    assert core == states.StateCore("snes9x2010", False, folder="Snes9x 2010")


@pytest.mark.parametrize("library_name", [None, "", "bad/name", 7])
def test_state_core_has_no_folder_activate_cannot_name(library_name):
    core = states.state_core_for(
        _snes("retroarch:bsnes"),
        {"core": "bsnes", "core_tier": "vetted", "library_name": library_name},
    )
    assert core == states.StateCore("bsnes", False)
    assert core.filed_as == "bsnes"


def test_state_core_takes_the_folder_from_the_cores_route_before_launch():
    reply = {
        "platform": "snes",
        "default": "snes9x",
        "cores": [
            {"core": "snes9x", "library_name": "Snes9x"},
            {"core": "snes9x2010", "library_name": "Snes9x 2010"},
        ],
    }
    with patch("handler.streaming.broker.request", return_value=reply) as request:
        configured = states.state_core_for(_snes("retroarch:snes9x2010"))
        default = states.state_core_for(_snes("retroarch"))
    assert configured == states.StateCore("snes9x2010", False, folder="Snes9x 2010")
    assert default == states.StateCore("snes9x", True, folder="snes9x")
    # Both answered from one cached reply.
    assert request.call_count == 1


def test_state_core_ignores_a_malformed_cores_row():
    reply = {
        "platform": "snes",
        "default": "snes9x",
        "cores": ["snes9x", {"core": 3}, {"core": "bsnes", "library_name": 4}],
    }
    with patch("handler.streaming.broker.request", return_value=reply):
        core = states.state_core_for(_snes("retroarch:bsnes"))
    assert core == states.StateCore("bsnes", False)


def test_state_core_asks_an_unreachable_broker_once():
    """Nothing is cached when it is down, so the folder lookup must not wait
    out a second timeout."""
    import urllib.error

    with patch(
        "handler.streaming.broker.request",
        side_effect=urllib.error.URLError("broker down"),
    ) as request:
        core = states.state_core_for(_snes("retroarch:bsnes"))
    assert core == states.StateCore("bsnes", False)
    assert request.call_count == 1


def test_no_state_core_outside_retroarch():
    assert states.state_core_for(_resolved(_webstation())) is None


def test_user_states_narrow_to_a_core(rom: Rom, admin_user: User):
    _core_state(rom, admin_user, "A.state", None)
    _core_state(rom, admin_user, "B.state", "bsnes")
    _core_state(rom, admin_user, "C.state", "snes9x")

    def names(core):
        found = states.user_states_for_emulator(
            admin_user.id, rom.id, "retroarch", core
        )
        return sorted(s.file_name for s in found)

    assert names(None) == ["A.state", "B.state", "C.state"]
    assert names(states.StateCore("bsnes", False)) == ["B.state"]
    assert names(states.StateCore("snes9x", True)) == ["A.state", "C.state"]


def test_pull_state_to_library_runs_for_a_webstation_container(
    rom: Rom, admin_user: User
):
    """RomM is the library of states on this protocol too, so a save has to come
    back out of the container rather than wait for the exit archive."""
    container = _webstation_for(rom)
    scanned = _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    with (
        patch(
            "handler.streaming.states.fetch_state_file",
            return_value=states.PulledState("Game.03.p2s", b"state-bytes"),
        ),
        patch("handler.streaming.states.fetch_state_screenshot", return_value=None),
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch("handler.asset_store.scan_state", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            states.pull_state_to_library(admin_user.id, rom.id, _resolved(container), 3)
        )
    assert ok is True
    assert (
        db_state_handler.get_state_by_filename(
            user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
        )
        is not None
    )


def test_webstation_resume_state_is_pushed_after_activate(
    client, access_token, rom: Rom, admin_user: User
):
    """The state-file route only answers while a session is up, and the session
    starts at activate, so pushing first would be refused. The broker's deferred
    load waits for the file, which is what makes the later push still land."""
    state = _add_state(rom, admin_user, "Game.03.p2s", "pcsx2")
    order = MagicMock()
    order.activate.return_value = {"url": "/room/x"}
    order.push.return_value = True
    with _streaming(_webstation_for(rom)):
        with (
            patch("handler.streaming.webstation.activate", order.activate),
            patch("handler.streaming.states.push_state_file", order.push),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "handler.filesystem.fs_asset_handler.read_file",
                new=AsyncMock(return_value=b"state-bytes"),
            ),
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id, state_id=state.id)
    assert r.status_code == 202
    assert _launch_ready(sent)["resume"] is True
    assert [c[0] for c in order.mock_calls if c[0] in ("activate", "push")] == [
        "activate",
        "push",
    ]
    assert order.activate.call_args.kwargs["resume_slot"] == 3
    assert order.push.call_args[0][1] == "Game.03.p2s"


@pytest.mark.parametrize(
    ("emulator", "name"),
    [
        ("duckstation", "SLUS-00594_resume.20260918-010000000000.sav"),
        ("rpcs3", "BLUS30443_1.20260918-010000000000.SAVESTAT"),
    ],
)
def test_an_exit_state_resume_is_the_activate_slot_alone(
    client, access_token, rom: Rom, admin_user: User, emulator, name
):
    """These brokers refuse a state file mid-session and resume from the exit
    state the save archive brings back, so the slot on the activate is the whole
    resume. A push would only be refused and report the resume as lost."""
    state = _add_state(rom, admin_user, name, emulator)
    activate = MagicMock(return_value={"url": "/room/x"})
    push = MagicMock(return_value=False)
    with _streaming({**_webstation_for(rom), "emulator": emulator}):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch("handler.streaming.states.push_state_file", push),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.tar"),
            ),
            patch(
                "handler.filesystem.fs_asset_handler.read_file",
                new=AsyncMock(return_value=b"state-bytes"),
            ),
            patch("handler.streaming.background.spawn_sync_task"),
            patch(
                "handler.streaming.states.hydrate_states_to_broker", new=MagicMock()
            ) as hydrate,
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id, state_id=state.id)
    assert r.status_code == 202
    assert activate.call_args.kwargs["resume_slot"] == 0
    push.assert_not_called()
    assert _launch_ready(sent)["resume"] is True
    assert hydrate.call_args.kwargs["resume_pushed"] is True


@pytest.mark.parametrize(
    ("emulator", "older_name", "newer_name"),
    [
        (
            "duckstation",
            "SLUS-00594_resume.20260917-010000000000.sav",
            "SLUS-00594_resume.20260918-010000000000.sav",
        ),
        (
            "rpcs3",
            "BLUS30443_1.20260917-010000000000.SAVESTAT",
            "BLUS30443_1.20260918-010000000000.SAVESTAT",
        ),
    ],
)
def test_an_older_exit_state_resume_rides_the_import_archive(
    client, access_token, rom: Rom, admin_user: User, emulator, older_name, newer_name
):
    """Picking anything but the newest capture on one of these containers must
    still reach the game: the save archive on its own only ever carries the
    newest exit state, so an older pick needs the import channel or it is
    silently swapped for a state the player never chose."""
    older = _add_state(rom, admin_user, older_name, emulator)
    _add_state(rom, admin_user, newer_name, emulator)
    activate = MagicMock(return_value={"url": "/room/x"})
    upload = MagicMock(return_value="rom-1.zip")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}),
        state_channel="archive",
        state_slot=0,
    )
    with _streaming({**_webstation_for(rom), "emulator": emulator}):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=spec
            ),
            patch(
                "handler.streaming.imports.fs_asset_handler.read_file",
                new=AsyncMock(side_effect=lambda path: path.encode()),
            ),
            patch("handler.streaming.imports.webstation.upload_archive", upload),
            patch("handler.streaming.background.spawn_sync_task"),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id, state_id=older.id)
    assert r.status_code == 202
    upload.assert_called_once()
    uploaded_bytes = upload.call_args.args[2]
    with zipfile.ZipFile(io.BytesIO(uploaded_bytes)) as zf:
        assert any(name.startswith(".import/state/") for name in zf.namelist())
    assert _launch_ready(sent)["resume"] is True


def test_an_older_exit_state_stays_off_the_import_path_without_broker_support(
    client, access_token, rom: Rom, admin_user: User
):
    """A broker that predates imports would never place an `.import/` member,
    so the archive goes out untouched and the resume is reported lost rather
    than claiming the archive's own exit state was the pick."""
    older = _add_state(
        rom,
        admin_user,
        "SLUS-00594_resume.20260917-010000000000.sav",
        "duckstation",
    )
    _add_state(
        rom,
        admin_user,
        "SLUS-00594_resume.20260918-010000000000.sav",
        "duckstation",
    )
    hydrate_import = AsyncMock()
    run_launch_mock = AsyncMock()
    with _streaming({**_webstation_for(rom), "emulator": "duckstation"}):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=None
            ),
            patch("handler.streaming.imports.hydrate_import_archive", hydrate_import),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.zip"),
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, state_id=older.id)
    assert r.status_code == 202
    hydrate_import.assert_not_called()
    assert run_launch_mock.call_args.kwargs["resume_import"] == "lost"
    assert run_launch_mock.call_args.kwargs["archive_path"] == "/romm/saves/archive.zip"


def test_a_rewritten_older_state_is_still_not_the_archives_capture(
    client, access_token, rom: Rom, admin_user: User
):
    older = _add_state(
        rom,
        admin_user,
        "SLUS-00594_resume.20260917-010000000000.sav",
        "duckstation",
    )
    _add_state(
        rom,
        admin_user,
        "SLUS-00594_resume.20260918-010000000000.sav",
        "duckstation",
    )
    db_state_handler.update_state(
        older.id, {"updated_at": datetime.now(timezone.utc) + timedelta(days=1)}
    )
    run_launch_mock = AsyncMock()
    with _streaming({**_webstation_for(rom), "emulator": "duckstation"}):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=None
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.zip"),
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(client, access_token, rom.id, state_id=older.id)
    assert r.status_code == 202
    assert run_launch_mock.call_args.kwargs["resume_import"] == "lost"


def _duckstation_pairing(rom: Rom, user: User) -> tuple[Save, Save, State]:
    """An older and a newer DuckStation archive, plus the newest capture."""
    older, newer = (
        _add_save(rom, user, f"Game [duckstation {tag}].saves.zip", "duckstation", tag)
        for tag in ("a", "b")
    )
    state = _add_state(rom, user, "SLUS-00594_resume.sav", "duckstation")
    return older, newer, state


def _clearing_duckstation(rom: Rom) -> dict[str, Any]:
    return {
        **_webstation_for(rom),
        "emulator": "duckstation",
        "clears_stale_saves": True,
    }


def test_an_older_save_with_the_newest_state_imports_the_picked_state(
    client, access_token, rom: Rom, admin_user: User
):
    """The older archive only carries its own exit state, so the picked state
    rides the import archive on top of it instead of being silently swapped."""
    older, _, state = _duckstation_pairing(rom, admin_user)
    activate = MagicMock(return_value={"url": "/room/x"})
    upload = MagicMock(return_value="rom-1.zip")
    spec = webstation.ImportSpec(
        kinds=frozenset({"state"}), state_channel="archive", state_slot=0
    )
    with _streaming(_clearing_duckstation(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=spec
            ),
            patch(
                "handler.streaming.imports.fs_asset_handler.read_file",
                new=AsyncMock(side_effect=lambda path: path.encode()),
            ),
            patch("handler.streaming.imports.webstation.upload_archive", upload),
            patch("handler.streaming.background.spawn_sync_task"),
        ):
            with _pushes() as sent:
                r = _claim(
                    client, access_token, rom.id, state_id=state.id, save_id=older.id
                )
    assert r.status_code == 202
    with zipfile.ZipFile(io.BytesIO(upload.call_args.args[2])) as zf:
        assert any(name.startswith(".import/state/") for name in zf.namelist())
    assert _launch_ready(sent)["resume"] is True


def test_an_older_save_with_the_newest_state_asks_for_a_retry_when_the_broker_is_silent(
    client, access_token, rom: Rom, admin_user: User
):
    """Only an import resumes the picked state over the older archive, so an
    unanswered check asks for a retry rather than resuming another state."""
    older, _, state = _duckstation_pairing(rom, admin_user)
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_duckstation(rom)):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec",
                side_effect=webstation.ImportSpecUnavailable,
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.zip"),
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(
                client, access_token, rom.id, state_id=state.id, save_id=older.id
            )
        assert _session_raw(_clearing_duckstation(rom)) is None
    assert r.status_code == 503
    run_launch_mock.assert_not_called()


def test_an_older_save_with_the_newest_state_reports_the_resume_lost_without_imports(
    client, access_token, rom: Rom, admin_user: User
):
    """Without an import channel the older archive's own exit state would load,
    so the launch must not report the picked state as resumed."""
    older, _, state = _duckstation_pairing(rom, admin_user)
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_duckstation(rom)):
        with (
            patch(
                "handler.streaming.webstation.require_import_spec", return_value=None
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.zip"),
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(
                client, access_token, rom.id, state_id=state.id, save_id=older.id
            )
    assert r.status_code == 202
    assert run_launch_mock.call_args.kwargs["resume_import"] == "lost"


def test_the_newest_save_with_the_newest_state_resumes_from_the_archive(
    client, access_token, rom: Rom, admin_user: User
):
    """Naming the newest archive explicitly is the default pairing, so the
    archive's own exit state is the pick and nothing is imported."""
    _, newer, state = _duckstation_pairing(rom, admin_user)
    hydrate_import = AsyncMock()
    run_launch_mock = AsyncMock()
    with _streaming(_clearing_duckstation(rom)):
        with (
            patch("handler.streaming.webstation.require_import_spec") as spec,
            patch("handler.streaming.imports.hydrate_import_archive", hydrate_import),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.zip"),
            ),
            patch("handler.streaming.launch.run_launch", run_launch_mock),
        ):
            r = _claim(
                client, access_token, rom.id, state_id=state.id, save_id=newer.id
            )
    assert r.status_code == 202
    spec.assert_not_called()
    hydrate_import.assert_not_called()
    assert run_launch_mock.call_args.kwargs["resume_import"] == "none"


def test_an_exit_state_resume_with_no_archive_reports_the_resume_lost(
    client, access_token, rom: Rom, admin_user: User
):
    """The archive is the whole resume on these brokers, so without one the slot
    would load whatever the container last held and the player would not be told."""
    state = _add_state(rom, admin_user, "SLUS-00594_resume.sav", "duckstation")
    activate = MagicMock(return_value={"url": "/room/x"})
    with _streaming({**_webstation_for(rom), "emulator": "duckstation"}):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value=None),
            ),
            patch("handler.streaming.background.spawn_sync_task"),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            with _pushes() as sent:
                r = _claim(client, access_token, rom.id, state_id=state.id)
    assert r.status_code == 202
    assert activate.call_args.kwargs["resume_slot"] is None
    assert _launch_ready(sent)["resume"] is False


def test_webstation_claim_without_a_state_boots_clean(client, access_token, rom: Rom):
    """A restored archive puts in-game saves back, nothing more: no picked
    state means no resume_slot, even though the archive carries the exit
    state of the last session."""
    activate = MagicMock(return_value={"url": "/room/x"})
    with _streaming(_webstation_for(rom)):
        with (
            patch("handler.streaming.webstation.activate", activate),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value="/romm/saves/archive.tar"),
            ),
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
        ):
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert activate.call_args.kwargs["archive_path"] == "/romm/saves/archive.tar"
    assert activate.call_args.kwargs["resume_slot"] is None


def test_stopping_a_webstation_broker_reports_the_state_it_captured(rom: Rom):
    """Stopping this broker is an exit and its exit saves, so the slot has to
    come back out: the caller is the only one who can file that state."""
    container = _webstation_for(rom)
    with patch(
        "handler.streaming.webstation.exit_session",
        return_value={"state_saved": True, "state_slot": 10},
    ):
        assert commands.stop(_resolved(container)) == (10, True)
    with patch(
        "handler.streaming.webstation.exit_session",
        return_value={"state_saved": False, "state_slot": 10},
    ):
        assert commands.stop(_resolved(container)) == (None, True)
    with patch("handler.streaming.webstation.exit_session", return_value=None):
        assert commands.stop(_resolved(container)) == (None, False)


def test_stopping_without_saving_asks_the_broker_to_write_no_state(rom: Rom):
    """A player leaving without saving must not have a state written for them,
    and nothing comes back for the caller to file."""
    container = _webstation_for(rom)
    with patch(
        "handler.streaming.webstation.exit_session",
        return_value={"state_saved": False, "state_slot": None},
    ) as exit_call:
        assert commands.stop(_resolved(container), save=False).state_slot is None
    assert exit_call.call_args.kwargs["save"] is False


def test_a_webstation_exit_carries_slot_zero_rather_than_dropping_it(rom: Rom):
    """Slot 0 is this broker's working slot, so it has to reach the request:
    omitting it would silently fall back to the broker's own default."""
    container = _webstation_for(rom)
    with patch("handler.streaming.broker.request_safe", return_value={}) as req:
        webstation.exit_session(_resolved(container), slot=0)
        assert "slot=0" in req.call_args[0][1]
        assert "save=0" not in req.call_args[0][1]
        webstation.exit_session(_resolved(container), slot=0, save=False)
        assert "save=0" in req.call_args[0][1]


def test_stopping_a_legacy_broker_reports_no_state(rom: Rom):
    """The per-emulator brokers stop without saving, so nothing is pulled."""
    with patch("handler.streaming.broker.request_safe", return_value={}):
        assert commands.stop(_resolved(_container_for(rom))) == (None, False)


def test_releasing_a_webstation_session_pulls_the_exit_state(
    client, access_token, rom: Rom
):
    """A player who closes the tab still exits the broker, and that exit takes a
    state. Leaving it in the container is how the last minutes of a session got
    lost whenever the save-and-exit button was not the way out."""
    pull = AsyncMock(return_value=True)
    with _streaming(_webstation_for(rom)):
        with (
            patch(
                "handler.streaming.webstation.activate",
                return_value={"url": "/room/x"},
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value=None),
            ),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
            _spawns_nothing(),
        ):
            _claim_ok(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.webstation.exit_session",
                return_value={"state_saved": True, "state_slot": 10},
            ),
            patch("handler.streaming.states.pull_state_to_library", pull),
            _spawns_nothing(),
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    pull.assert_awaited_once()
    assert pull.await_args is not None
    assert pull.await_args.args[1:] == (rom.id, _resolved(_webstation_for(rom)), 10)


def test_releasing_without_saving_files_no_state(client, access_token, rom: Rom):
    """The stop button is the deliberate way out without saving, so the exit
    writes nothing and there is no state to pull into the library."""
    pull = AsyncMock(return_value=True)
    stop = MagicMock(return_value=commands.StopOutcome())
    with _streaming(_webstation_for(rom)):
        with (
            patch(
                "handler.streaming.webstation.activate",
                return_value={"url": "/room/x"},
            ),
            patch(
                "handler.streaming.saves.hydrate_saves_to_webstation",
                new=AsyncMock(return_value=None),
            ),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
            _spawns_nothing(),
        ):
            _claim_ok(client, access_token, rom.id)
        with (
            patch("handler.streaming.commands.stop", stop),
            patch("handler.streaming.states.pull_state_to_library", pull),
            _spawns_nothing(),
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}?save=false",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert stop.call_args[0][1] is False
    pull.assert_not_awaited()


# ── Auth guards ───────────────────────────────────────────────────────────────


def test_claim_session_requires_auth(client):
    assert client.post("/api/streaming/sessions", json={"rom_id": 1}).status_code == 401


def test_release_session_requires_auth(client):
    assert client.delete("/api/streaming/sessions/ps2").status_code == 401


def test_force_release_all_requires_auth(client):
    assert client.delete("/api/streaming/sessions").status_code == 401


def test_list_sessions_requires_auth(client):
    assert client.get("/api/streaming/sessions").status_code == 401


def test_list_sessions_requires_admin(client, viewer_access_token):
    r = client.get("/api/streaming/sessions", headers=_auth(viewer_access_token))
    assert r.status_code == 403


def test_list_sessions_returns_enriched_entries(
    client, access_token, viewer_access_token, viewer_user, rom: Rom
):
    """The admin list carries platform, rom and username for the release UI."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        r = client.get("/api/streaming/sessions", headers=_auth(access_token))
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 1
    entry = sessions[0]
    assert entry["container"] == "http://192.168.1.10:8000"
    assert entry["platform"] == rom.platform_slug
    assert entry["rom_id"] == rom.id
    assert entry["username"] == viewer_user.username
    assert entry["claimed_at"]


def test_admin_can_release_other_users_session(
    client, access_token, viewer_access_token, rom: Rom
):
    """An admin may release a session claimed by someone else."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, viewer_access_token, rom.id)
        with _stub_stop() as stop:
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"
    stop.assert_called_once()


# ── Whole memory-card sync ────────────────────────────────────────────────────


def _mc_container_for(rom: Rom, broker_host="http://192.168.1.10:8000"):
    """A container on whole-card sync, namespaced to the pcsx2 emulator."""
    return {
        **_container_for(rom, broker_host),
        "emulator": "pcsx2",
        "memory_card_sync": True,
    }


def _mc_claim(client, token, rom_id, memory_card_id=None, card_import=None):
    body: dict[str, Any] = {"rom_id": rom_id}
    if memory_card_id is not None:
        body["memory_card_id"] = memory_card_id
    if card_import is not None:
        body["card_import"] = card_import
    return client.post("/api/streaming/sessions", json=body, headers=_auth(token))


def _make_card(user: User, emulator="pcsx2", name="My PS2 card", is_public=False):
    return db_memory_card_handler.add_card(
        MemoryCard(
            user_id=user.id,
            emulator=emulator,
            platform_id=None,
            name=name,
            slot=1,
            is_public=is_public,
        )
    )


def _card_version(card_id: int, file_name: str, content_hash: str | None):
    name_no_ext, _, extension = file_name.rpartition(".")
    return MemoryCardVersion(
        memory_card_id=card_id,
        file_name=file_name,
        file_name_no_tags=name_no_ext,
        file_name_no_ext=name_no_ext,
        file_extension=extension,
        content_hash=content_hash,
        file_path=f"users/1/memory_cards/pcsx2/{card_id}",
        file_size_bytes=1.0,
    )


def test_resolve_memory_card_explicit_owned(admin_user: User):
    card = _make_card(admin_user)
    resolved = memory_cards.resolve_card(admin_user.id, "pcsx2", card.id)
    assert resolved is not None
    assert resolved.id == card.id


def test_resolve_memory_card_wrong_emulator_404(admin_user: User):
    card = _make_card(admin_user, emulator="dolphin")
    with pytest.raises(HTTPException) as exc:
        memory_cards.resolve_card(admin_user.id, "pcsx2", card.id)
    assert exc.value.status_code == 404


def test_resolve_memory_card_foreign_id_404(admin_user: User, viewer_user: User):
    """An id owned by another user is not resolvable, even if public."""
    card = _make_card(viewer_user, is_public=True)
    with pytest.raises(HTTPException) as exc:
        memory_cards.resolve_card(admin_user.id, "pcsx2", card.id)
    assert exc.value.status_code == 404


def test_resolve_memory_card_default_most_recent(admin_user: User):
    older = _make_card(admin_user, name="older")
    newer = _make_card(admin_user, name="newer")
    # Server-default timestamps share a second, so pin the ordering explicitly.
    db_memory_card_handler.update_card(
        older.id, {"updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    )
    db_memory_card_handler.update_card(
        newer.id, {"updated_at": datetime(2026, 6, 1, tzinfo=timezone.utc)}
    )
    resolved = memory_cards.resolve_card(admin_user.id, "pcsx2", None)
    assert resolved is not None
    assert resolved.id == newer.id


def test_resolve_memory_card_none_when_user_has_no_card(admin_user: User):
    """Resolution never creates rows; a cardless user resolves to None so the
    claim path can defer creation until the claim is won."""
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    assert memory_cards.resolve_card(admin_user.id, "pcsx2", None) is None
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_create_blank_memory_card(admin_user: User, rom: Rom):
    """First play on an emulator with no card creates a blank owned card."""
    created = memory_cards.create_blank_card(admin_user.id, "pcsx2", rom.platform_id)
    assert created.id is not None
    assert created.user_id == admin_user.id
    assert created.emulator == "pcsx2"
    assert created.platform_id == rom.platform_id
    assert created.is_public is False
    assert db_memory_card_handler.get_latest_version(created.id) is None


def test_hydrate_memory_card_pushes_latest_version(admin_user: User, rom: Rom):
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(card.id, "My PS2 card [2026-07-12 10-00-00].card.zip", "h1")
    )
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"card-bytes"),
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
    ):
        ok = asyncio.run(
            memory_cards.hydrate_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == b"card-bytes"


def test_hydrate_blank_card_wipes_container(admin_user: User, rom: Rom):
    """A card with no version pushes the empty zip so the container is wiped."""
    card = _make_card(admin_user)
    with patch("handler.streaming.memory_cards.push_card", return_value=True) as push:
        ok = asyncio.run(
            memory_cards.hydrate_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == memory_cards.EMPTY_CARD


def test_hydrate_missing_file_wipes_to_blank(admin_user: User, rom: Rom):
    """A version row whose file is gone must wipe to blank, never leak."""
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(card.id, "My PS2 card [gone].card.zip", "h1")
    )
    with (
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
    ):
        ok = asyncio.run(
            memory_cards.hydrate_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == memory_cards.EMPTY_CARD


def test_hydrate_returns_false_on_push_failure(admin_user: User, rom: Rom):
    card = _make_card(admin_user)
    with patch("handler.streaming.memory_cards.push_card", return_value=False):
        ok = asyncio.run(
            memory_cards.hydrate_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is False


def test_store_memory_card_version_stores_new(admin_user: User):
    card = _make_card(admin_user)
    scanned = _card_version(card.id, "My PS2 card [new].card.zip", "hash-new")
    with (
        patch("utils.memory_cards.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch(
            "utils.memory_cards.scan_memory_card_version",
            new=AsyncMock(return_value=scanned),
        ),
    ):
        stored = asyncio.run(
            memory_cards.store_memory_card_version(admin_user, card, b"card-bytes")
        )
    assert stored is not None
    wf.assert_awaited_once()
    latest = db_memory_card_handler.get_latest_version(card.id)
    assert latest is not None
    assert latest.content_hash == "hash-new"


def test_store_memory_card_version_dedups_identical(admin_user: User):
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(card.id, "My PS2 card [old].card.zip", "dup")
    )
    scanned = _card_version(card.id, "My PS2 card [new].card.zip", "dup")
    with (
        patch("utils.memory_cards.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "utils.memory_cards.scan_memory_card_version",
            new=AsyncMock(return_value=scanned),
        ),
        patch("utils.memory_cards.fs_asset_handler.remove_file", new=AsyncMock()) as rm,
    ):
        stored = asyncio.run(
            memory_cards.store_memory_card_version(admin_user, card, b"card-bytes")
        )
    assert stored is None
    rm.assert_awaited_once()
    assert len(db_memory_card_handler.get_versions(card.id)) == 1


def test_evacuate_memory_card_stores_snapshot(admin_user: User, rom: Rom):
    card = _make_card(admin_user)
    with (
        patch("handler.streaming.memory_cards.fetch_card", return_value=b"card-bytes"),
        patch(
            "handler.streaming.memory_cards.store_memory_card_version",
            new=AsyncMock(return_value=True),
        ) as store,
    ):
        ok = asyncio.run(
            memory_cards.evacuate_card(admin_user.id, card.id, _mc_container_for(rom))
        )
    assert ok is True
    store.assert_awaited_once()


def test_evacuate_memory_card_confirmed_empty_is_safe_to_wipe(
    admin_user: User, rom: Rom
):
    """A broker-confirmed empty slot (fetch returns None) stores nothing but is
    safe to wipe, so evacuation reports True."""
    card = _make_card(admin_user)
    with (
        patch("handler.streaming.memory_cards.fetch_card", return_value=None),
        patch(
            "handler.streaming.memory_cards.store_memory_card_version", new=AsyncMock()
        ) as store,
    ):
        ok = asyncio.run(
            memory_cards.evacuate_card(admin_user.id, card.id, _mc_container_for(rom))
        )
    assert ok is True
    store.assert_not_awaited()


def test_evacuate_memory_card_unavailable_is_not_safe_to_wipe(
    admin_user: User, rom: Rom
):
    """When the card cannot be read (endpoint missing, wrong card type, transport
    error), evacuation must report False so the slot is never wiped."""
    card = _make_card(admin_user)
    with (
        patch(
            "handler.streaming.memory_cards.fetch_card",
            side_effect=memory_cards.MemoryCardUnavailable("boom"),
        ),
        patch(
            "handler.streaming.memory_cards.store_memory_card_version", new=AsyncMock()
        ) as store,
    ):
        ok = asyncio.run(
            memory_cards.evacuate_card(admin_user.id, card.id, _mc_container_for(rom))
        )
    assert ok is False
    store.assert_not_awaited()


def _http_error(code: int, headers: dict[str, str] | None = None):
    import http.client
    import urllib.error

    hdrs = http.client.HTTPMessage()
    for name, value in (headers or {}).items():
        hdrs[name] = value
    return urllib.error.HTTPError("http://broker/memory-card", code, "err", hdrs, None)


def test_raise_http_error_raises_import_refused_as_a_typed_error():
    """A refused import must reach the caller as structured data, not folded
    into the generic 502 string every other broker error becomes."""
    payload = json.dumps(
        {
            "detail": {
                "error": "import_refused",
                "refusals": [
                    {
                        "reason": "shape_mismatch",
                        "member": ".import/save/Game.mcr",
                        "expected": "folder",
                        "detail": "wanted a directory member",
                        "suggest_emulator": None,
                        "docs": None,
                    }
                ],
                "truncated": 0,
            }
        }
    ).encode()
    exc = _http_error(422)
    with patch.object(exc, "read", side_effect=_reads(payload)):
        with pytest.raises(broker.ImportRefusedError) as raised:
            broker.raise_http_error(exc)
    assert raised.value.truncated == 0
    assert len(raised.value.refusals) == 1
    assert raised.value.refusals[0].reason == "shape_mismatch"
    assert raised.value.refusals[0].member == ".import/save/Game.mcr"


def test_raise_http_error_parses_a_refusal_list_at_the_brokers_cap():
    import http.client
    import urllib.error

    refusal = {
        "reason": "unrecognised_layout",
        "expected": "<card>/" + "x" * 200,
        "detail": "plan is partial: other members were refused",
        "suggest_emulator": None,
        "docs": "/docs/api/imports#unrecognised-layout",
    }
    payload = json.dumps(
        {
            "detail": {
                "error": "import_refused",
                "refusals": [
                    {**refusal, "member": f".import/save/card/{i:04d}/" + "y" * 100}
                    for i in range(200)
                ],
                "truncated": 40,
            }
        }
    ).encode()
    assert len(payload) > 64 * 1024
    exc = urllib.error.HTTPError(
        "http://broker/activate",
        422,
        "err",
        http.client.HTTPMessage(),
        io.BytesIO(payload),
    )
    with pytest.raises(broker.ImportRefusedError) as raised:
        broker.raise_http_error(exc)
    assert len(raised.value.refusals) == 200
    assert raised.value.truncated == 40


def test_raise_http_error_keeps_a_long_plain_error_out_of_the_502_detail():
    exc = _http_error(500)
    with patch.object(exc, "read", side_effect=_reads(b"x" * (100 * 1024))):
        with pytest.raises(HTTPException) as raised:
            broker.raise_http_error(exc)
    assert len(raised.value.detail) < 9 * 1024


def test_raise_http_error_still_raises_502_for_a_plain_broker_error():
    """An ordinary broker error (not an import refusal) is still a plain 502."""
    exc = _http_error(500)
    with patch.object(exc, "read", side_effect=_reads(b"boom")):
        with pytest.raises(HTTPException) as raised:
            broker.raise_http_error(exc)
    assert raised.value.status_code == 502


def test_broker_error_body_gives_up_on_a_slow_body():
    exc = _http_error(500)
    with (
        patch.object(exc, "read", side_effect=_reads(b"boom")),
        patch("handler.streaming.broker._BROKER_ERROR_READ_SECONDS", -1),
    ):
        assert broker.broker_error_body(exc) == ""


def test_fetch_memory_card_returns_bytes(rom: Rom):
    resp = MagicMock()
    resp.__enter__.return_value.read.side_effect = _reads(b"card-bytes")
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        assert (
            memory_cards.fetch_card(_resolved(_mc_container_for(rom))) == b"card-bytes"
        )


def test_fetch_memory_card_absent_header_returns_none(rom: Rom):
    """A 404 tagged X-Memory-Card: absent means the slot is genuinely empty."""
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=_http_error(404, {"X-Memory-Card": "absent"}),
    ):
        assert memory_cards.fetch_card(_resolved(_mc_container_for(rom))) is None


def test_fetch_memory_card_unmarked_404_raises(rom: Rom):
    """An untagged 404 (endpoint missing on an old broker) must NOT be mistaken
    for an empty slot; it raises so the card is never wiped."""
    with patch(
        "handler.streaming.broker.urllib.request.urlopen", side_effect=_http_error(404)
    ):
        with pytest.raises(memory_cards.MemoryCardUnavailable):
            memory_cards.fetch_card(_resolved(_mc_container_for(rom)))


def test_fetch_memory_card_file_card_409_raises(rom: Rom):
    with patch(
        "handler.streaming.broker.urllib.request.urlopen", side_effect=_http_error(409)
    ):
        with pytest.raises(memory_cards.MemoryCardUnavailable):
            memory_cards.fetch_card(_resolved(_mc_container_for(rom)))


def test_fetch_memory_card_transport_error_raises(rom: Rom):
    import urllib.error

    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=urllib.error.URLError("broker down"),
    ):
        with pytest.raises(memory_cards.MemoryCardUnavailable):
            memory_cards.fetch_card(_resolved(_mc_container_for(rom)))


def test_import_spec_parses_the_brokers_discovery_response(rom: Rom):
    body = json.dumps(
        {
            "import_api": 1,
            "manifest_version": 2,
            "kinds": [
                {
                    "kind": "save",
                    "shapes": ["folder"],
                    "requires_resume_slot": False,
                    "max_members": 8,
                },
                {
                    "kind": "state",
                    "shapes": ["file"],
                    "requires_resume_slot": True,
                    "max_members": 1,
                },
            ],
            "state_channel": "archive",
            "state_slot": 0,
        }
    ).encode()
    resp = MagicMock()
    resp.__enter__.return_value.read.side_effect = _reads(body)
    resp.__enter__.return_value.status = 200
    with patch("handler.streaming.broker.urllib.request.urlopen", return_value=resp):
        spec = webstation.import_spec(
            _resolved(_webstation_for(rom)), "dolphin", rom.platform_slug
        )
    assert spec is not None
    assert spec.state_channel == "archive"
    assert spec.state_slot == 0
    assert spec.accepts("save")
    assert spec.accepts("state")
    assert not spec.accepts("memcard")


def test_import_spec_returns_none_and_caches_on_404(rom: Rom):
    """A broker that predates imports answers 404; that answer is stable
    enough to cache rather than re-check every claim."""
    container = _resolved(_webstation_for(rom))
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=_http_error(404),
    ) as urlopen:
        first = webstation.import_spec(container, "dolphin", rom.platform_slug)
        second = webstation.import_spec(container, "dolphin", rom.platform_slug)
    assert first is None
    assert second is None
    assert urlopen.call_count == 1


def _spec_path(container) -> str:
    """The path import_spec asks the broker for."""
    with patch(
        "handler.streaming.broker.request", side_effect=_http_error(404)
    ) as request:
        webstation.import_spec(container, "retroarch", "snes")
    path: str = request.call_args.args[1]
    return path


def test_import_spec_asks_about_the_configured_core():
    """Discovery must answer for the core activate boots, or the picker offers
    imports that core refuses."""
    path = _spec_path(_snes("retroarch:bsnes"))
    assert "&core=bsnes" in path
    assert "experimental_cores" not in path


def test_import_spec_carries_the_opt_in():
    opted = _snes("retroarch:bsnes", experimental_cores=True)
    assert _spec_path(opted).endswith("&core=bsnes&experimental_cores=1")


def test_import_spec_query_is_unchanged_without_a_core():
    assert "core=" not in _spec_path(_snes("retroarch"))


def test_import_spec_asks_again_when_the_core_changes():
    """A 404/422 is cached, so a key without the core would keep the old
    core's answer after a config edit."""
    with patch(
        "handler.streaming.broker.request", side_effect=_http_error(404)
    ) as request:
        webstation.import_spec(_snes("retroarch:bsnes"), "retroarch", "snes")
        webstation.import_spec(_snes("retroarch"), "retroarch", "snes")
        webstation.import_spec(
            _snes("retroarch:bsnes", experimental_cores=True), "retroarch", "snes"
        )
    assert request.call_count == 3


def test_import_spec_asks_again_after_refusing_a_core():
    """A refused core is fixed by upgrading the broker, which must not take a
    RomM restart to notice."""
    container = _snes("retroarch:bsnes")
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request", side_effect=_http_error(422)
    ) as request:
        webstation.import_spec(container, "retroarch", "snes")
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            webstation.import_spec(container, "retroarch", "snes")
    assert request.call_count == 2


def test_import_spec_never_asks_a_legacy_broker(rom: Rom):
    """Declared imports are a webstation contract; a per-emulator broker is
    never asked, so a foreign pick there is refused without a round trip."""
    with patch("handler.streaming.broker.urllib.request.urlopen") as urlopen:
        spec = webstation.import_spec(
            _resolved(_container_for(rom)), "pcsx2", rom.platform_slug
        )
    assert spec is None
    urlopen.assert_not_called()


def test_import_spec_returns_none_uncached_on_a_transient_failure(rom: Rom):
    """A network blip is not the same stable answer a 404/422 is, so it must
    never be cached (a future call should try again)."""
    container = _resolved(_webstation_for(rom))
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=OSError("unreachable"),
    ) as urlopen:
        first = webstation.import_spec(container, "dolphin", rom.platform_slug)
        second = webstation.import_spec(container, "dolphin", rom.platform_slug)
    assert first is None
    assert second is None
    assert urlopen.call_count == 2


def test_import_spec_asks_again_once_a_404_expires(rom: Rom):
    """Upgrading the broker adds the route, which must not take a RomM restart
    to notice."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_MISSING_TTL + 1
    with patch(
        "handler.streaming.broker.request", side_effect=_http_error(404)
    ) as request:
        webstation.import_spec(container, "dolphin", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            webstation.import_spec(container, "dolphin", rom.platform_slug)
    assert request.call_count == 2


_SAVE_SPEC_BODY = {
    "kinds": [{"kind": "save", "shapes": ["<name>.srm"], "max_members": 1}],
    "state_channel": "push",
    "state_slot": 10,
}


def test_import_spec_keeps_the_last_answer_through_a_failed_check(rom: Rom):
    """One slow reply must not hide the save picker or refuse a foreign pick
    the broker took a moment ago."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request",
        side_effect=[_SAVE_SPEC_BODY, OSError("timed out")],
    ):
        first = webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            second = webstation.require_import_spec(
                container, "retroarch", rom.platform_slug
            )
    assert first is not None and first.accepts("save")
    assert second == first


def test_import_spec_holds_the_fallback_for_the_rest_of_a_claim(rom: Rom):
    """A claim checks the pool's reference and then the won container, which
    must not wait out the same broker timeout twice."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request",
        side_effect=[_SAVE_SPEC_BODY, OSError("timed out")],
    ) as request:
        first = webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            webstation.require_import_spec(container, "retroarch", rom.platform_slug)
            again = webstation.require_import_spec(
                container, "retroarch", rom.platform_slug
            )
    assert again == first
    assert request.call_count == 2


def test_import_spec_last_answer_reaches_every_worker(rom: Rom):
    """Each web worker has its own process, so an answer one of them got must
    stand in for a failed check on another, or the picker flickers by worker."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch("handler.streaming.broker.request", return_value=_SAVE_SPEC_BODY):
        first = webstation.import_spec(container, "retroarch", rom.platform_slug)
    # A fresh worker: nothing of the first one's process memory.
    fresh_worker: dict[str, Any] = {
        name: {}
        for name in vars(webstation)
        if name.startswith("_import_spec_") and isinstance(vars(webstation)[name], dict)
    }
    with (
        patch.multiple(webstation, **fresh_worker),
        patch("handler.streaming.broker.request", side_effect=OSError("timed out")),
        patch("handler.streaming.webstation.time.monotonic", return_value=later),
    ):
        second = webstation.require_import_spec(
            container, "retroarch", rom.platform_slug
        )
    assert second == first


def test_import_spec_treats_an_unreadable_last_answer_as_none(rom: Rom):
    """A cached answer in a shape this RomM doesn't read counts as no answer."""
    container = _resolved(_webstation_for(rom))
    with patch("handler.streaming.broker.request", return_value=_SAVE_SPEC_BODY):
        webstation.import_spec(container, "retroarch", rom.platform_slug)
    for key in sync_cache.scan_iter(f"{webstation._LAST_GOOD_KEY_PREFIX}*"):
        sync_cache.set(key, '{"kinds": "save"')
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with (
        patch("handler.streaming.broker.request", side_effect=OSError("timed out")),
        patch("handler.streaming.webstation.time.monotonic", return_value=later),
    ):
        with pytest.raises(webstation.ImportSpecUnavailable):
            webstation.require_import_spec(container, "retroarch", rom.platform_slug)


def test_import_spec_keeps_the_last_answer_through_a_404(rom: Rom):
    """A broker that answered before and 404s now is most likely restarting
    behind a proxy, so the picker keeps its imports and asks again soon."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    soon_after = later + webstation._IMPORT_SPEC_FALLBACK_TTL + 1
    with patch(
        "handler.streaming.broker.request",
        side_effect=[_SAVE_SPEC_BODY, _http_error(404), _http_error(404)],
    ) as request:
        first = webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            second = webstation.require_import_spec(
                container, "retroarch", rom.platform_slug
            )
        with patch(
            "handler.streaming.webstation.time.monotonic", return_value=soon_after
        ):
            third = webstation.require_import_spec(
                container, "retroarch", rom.platform_slug
            )
    assert second == first
    assert third == first
    assert request.call_count == 3


def test_import_spec_falls_back_on_a_server_error(rom: Rom):
    """A 5xx is the broker or its proxy failing for now, not an answer."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request",
        side_effect=[_SAVE_SPEC_BODY, _http_error(502)],
    ):
        first = webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            second = webstation.require_import_spec(
                container, "retroarch", rom.platform_slug
            )
    assert second == first


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(_http_error(401), id="refused-secret"),
        pytest.param(_http_error(400), id="bad-request"),
        pytest.param(ValueError("not json"), id="not-json"),
        pytest.param({"kinds": "save"}, id="unparsable"),
        pytest.param(["save"], id="not-an-object"),
    ],
)
def test_import_spec_reads_a_lasting_failure_as_no_imports(rom: Rom, answer):
    """Retrying can't fix a refused secret or a reply RomM can't read, so a pick
    gets an honest refusal rather than an endless "try again"."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request", side_effect=[_SAVE_SPEC_BODY, answer]
    ):
        webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            assert (
                webstation.require_import_spec(
                    container, "retroarch", rom.platform_slug
                )
                is None
            )
    # The stored answer survives, so fixing the config brings imports back.
    much_later = later + webstation._IMPORT_SPEC_TTL + 1
    with (
        patch("handler.streaming.broker.request", side_effect=OSError("timed out")),
        patch("handler.streaming.webstation.time.monotonic", return_value=much_later),
    ):
        assert (
            webstation.require_import_spec(container, "retroarch", rom.platform_slug)
            is not None
        )


def test_import_spec_caches_a_lasting_failure_briefly(rom: Rom):
    """A misconfigured broker is asked again soon, not on every check."""
    container = _resolved(_webstation_for(rom))
    later = time.monotonic() + webstation._IMPORT_SPEC_TTL + 1
    with patch(
        "handler.streaming.broker.request", side_effect=_http_error(401)
    ) as request:
        webstation.import_spec(container, "retroarch", rom.platform_slug)
        webstation.import_spec(container, "retroarch", rom.platform_slug)
        with patch("handler.streaming.webstation.time.monotonic", return_value=later):
            webstation.import_spec(container, "retroarch", rom.platform_slug)
    assert request.call_count == 2


def test_require_import_spec_raises_when_the_broker_never_answered(rom: Rom):
    """A launch has to tell "try again" from "this broker can't", which the
    picker's None doesn't."""
    container = _resolved(_webstation_for(rom))
    with patch(
        "handler.streaming.broker.urllib.request.urlopen",
        side_effect=OSError("unreachable"),
    ):
        with pytest.raises(webstation.ImportSpecUnavailable):
            webstation.require_import_spec(container, "dolphin", rom.platform_slug)


def test_claim_hydrates_memory_card_before_launch(client, access_token, rom: Rom):
    """On a sync container the whole card hydrates before launch, and the legacy
    per-file save path is skipped."""
    call_order = []

    def _note_launch(*a, **k):
        call_order.append("launch")

    def _note_card(*a, **k):
        call_order.append("card")
        return True

    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch", side_effect=_note_launch),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(side_effect=_note_card),
            ) as hydrate_card,
            patch(
                "handler.streaming.saves.hydrate_saves_to_broker", new=AsyncMock()
            ) as legacy,
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    hydrate_card.assert_awaited_once()
    legacy.assert_not_awaited()
    assert call_order == ["card", "launch"]


def test_claim_aborts_when_card_hydration_fails(
    client, access_token, admin_user: User, rom: Rom
):
    """A failed card hydration must free the claim and return 502, never launch
    a container that could still hold the previous player's card. The blank card
    auto-created for this claim must be cleaned up so an aborted claim leaks none."""
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch") as launch,
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=False),
            ),
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 502
    launch.assert_not_called()
    # The claim must be released so the container is not wedged.
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )
    # No orphan blank card survives the aborted claim.
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_claim_aborts_on_an_unexpected_error_after_the_blank_card(
    client, access_token, admin_user: User, rom: Rom
):
    """An error no step planned for still frees the container and its blank card."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch") as launch,
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.saves.wait_for_save_pull",
                new=AsyncMock(side_effect=RuntimeError("redis went away")),
            ),
            _spawns_nothing(),
            pytest.raises(RuntimeError, match="redis went away"),
        ):
            _mc_claim(client, access_token, rom.id)
    launch.assert_not_called()
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_claim_aborts_on_an_unexpected_error_keeps_the_players_card(
    client, access_token, admin_user: User, rom: Rom
):
    """Only a blank this claim created is discarded: the player's own card stays."""
    card = memory_cards.create_blank_card(admin_user.id, "pcsx2", rom.platform_id)
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.saves.wait_for_save_pull",
                new=AsyncMock(side_effect=RuntimeError("redis went away")),
            ),
            _spawns_nothing(),
            pytest.raises(RuntimeError),
        ):
            _mc_claim(client, access_token, rom.id, memory_card_id=card.id)
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )
    assert [c.id for c in db_memory_card_handler.get_cards(admin_user.id, "pcsx2")] == [
        card.id
    ]


def test_claim_releases_once_on_an_http_error_from_a_step(
    client, access_token, admin_user: User, rom: Rom
):
    """A step that raises an HTTPException without releasing anything still frees
    the container and its blank card, through a single release."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch") as launch,
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.saves.wait_for_save_pull",
                new=AsyncMock(side_effect=HTTPException(status_code=503)),
            ),
            patch(
                "handler.streaming.lifecycle.abort_claim",
                new=AsyncMock(wraps=lifecycle.abort_claim),
            ) as abort_claim,
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 503
    launch.assert_not_called()
    abort_claim.assert_awaited_once()
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_claim_releases_once_when_card_hydration_fails(
    client, access_token, admin_user: User, rom: Rom
):
    """A helper's own refusal is released by the claim alone, never twice."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "handler.streaming.lifecycle.abort_claim",
                new=AsyncMock(wraps=lifecycle.abort_claim),
            ) as abort_claim,
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 502
    abort_claim.assert_awaited_once()
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_claim_aborted_after_adopt_keeps_the_adopted_card(
    client, access_token, admin_user: User, rom: Rom
):
    """The adoption stays recorded, so the next claim must mount the adopted card."""
    card_bytes = _gci_card_bytes()
    container = _mc_container_for(rom)
    with _streaming(container):
        with (
            _adoption_storage(card_bytes),
            patch("handler.streaming.memory_cards.fetch_card", return_value=card_bytes),
            patch("handler.streaming.commands.launch"),
            patch(
                "handler.streaming.saves.wait_for_save_pull",
                new=AsyncMock(side_effect=RuntimeError("redis went away")),
            ),
            _spawns_nothing(),
            pytest.raises(RuntimeError),
        ):
            _mc_claim(client, access_token, rom.id, card_import="adopt")

        assert asyncio.run(session_store.get_session(_key_of(container))) is None
        cards = db_memory_card_handler.get_cards(admin_user.id, "pcsx2")
        assert len(cards) == 1
        assert db_memory_card_handler.get_latest_version(cards[0].id) is not None

        with (
            _adoption_storage(card_bytes),
            patch("handler.streaming.memory_cards.fetch_card") as fetch,
            patch(
                "handler.streaming.memory_cards.push_card", return_value=True
            ) as push,
            patch("handler.streaming.commands.launch"),
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    fetch.assert_not_called()
    assert push.call_args[0][1] == card_bytes
    assert [c.id for c in db_memory_card_handler.get_cards(admin_user.id, "pcsx2")] == [
        cards[0].id
    ]


def test_save_and_exit_evacuates_card(client, access_token, rom: Rom):
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            _spawns_nothing(),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 1, True),
            ),
            patch(
                "handler.streaming.memory_cards.evacuate_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch(
                "handler.streaming.memory_cards.wipe_session_card", new=AsyncMock()
            ) as wipe,
            patch("handler.streaming.saves.pull_saves_to_library") as legacy,
            patch("handler.streaming.states.pull_state_to_library", new=MagicMock()),
            _spawns_nothing(),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    evac.assert_awaited_once()
    # A successful evacuation wipes the slot as defense in depth.
    wipe.assert_awaited_once()
    legacy.assert_not_called()


def test_release_evacuates_card(client, access_token, rom: Rom):
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            _spawns_nothing(),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            _stub_stop() as stop,
            patch(
                "handler.streaming.memory_cards.evacuate_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch(
                "handler.streaming.memory_cards.wipe_session_card", new=AsyncMock()
            ) as wipe,
            patch("handler.streaming.background.spawn_sync_task") as spawn,
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    stop.assert_called_once()
    evac.assert_awaited_once()
    # A successful evacuation wipes the slot as defense in depth.
    wipe.assert_awaited_once()
    # Legacy per-file pull must not be scheduled on a sync container.
    spawn.assert_not_called()


def test_release_frees_the_claim_when_teardown_raises(client, access_token, rom: Rom):
    """The API has already reported the release, so a step that blows up must
    not leave the claim behind: the container would read occupied to everyone
    else until stale takeover or the TTL expires."""
    container = _mc_container_for(rom)
    with _streaming(container):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            _spawns_nothing(),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            _stub_stop(),
            patch(
                "handler.streaming.memory_cards.evacuate_session_card",
                new=AsyncMock(side_effect=OSError("broker went away")),
            ),
            _spawns_nothing(),
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert asyncio.run(session_store.get_session(_key_of(container))) is None


def test_save_and_exit_wait_false_forces_blocking_on_card_sync(
    client, access_token, rom: Rom
):
    """Whole-card sync must quiesce the emulator before evacuating, so a
    wait=false request still runs a blocking save+kill."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            _spawns_nothing(),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            patch(
                "handler.streaming.commands.save_and_exit",
                return_value=commands.SaveAndExitOutcome(True, 1, True),
            ) as save,
            patch(
                "handler.streaming.memory_cards.evacuate_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch("handler.streaming.memory_cards.wipe_session_card", new=AsyncMock()),
            patch("handler.streaming.states.pull_state_to_library", new=MagicMock()),
            _spawns_nothing(),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"wait": False},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert save.call_args.kwargs["wait"] is True
    evac.assert_awaited_once()


def test_lost_claim_race_does_not_create_blank_card(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """A claim that loses the SET NX race (409) must not leave an orphan blank
    card behind for a user who had none."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            _spawns_nothing(),
        ):
            assert _mc_claim(client, access_token, rom.id).status_code == 202
            assert db_memory_card_handler.get_cards(viewer_user.id, "pcsx2") == []
            r = _mc_claim(client, viewer_access_token, rom.id)
    assert r.status_code == 409
    assert db_memory_card_handler.get_cards(viewer_user.id, "pcsx2") == []


# ── First-claim card adoption ─────────────────────────────────────────────────


def _gci_card_bytes() -> bytes:
    """A container card holding one GameCube save."""
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("01-GXCE-CustomRobo-BattleRevolution.gci", b"x" * 100)
    return buf.getvalue()


@contextmanager
def _adoption_storage(card_bytes: bytes):
    """Run the real store-then-hydrate round trip against stubbed disk I/O, so
    the assertion is on what actually gets pushed back to the container."""

    async def _scan(file_name, user, emulator, card_id, content_hash=None):
        return _card_version(card_id, file_name, content_hash or "adopted-hash")

    with (
        patch("handler.asset_store.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "handler.filesystem.fs_asset_handler.read_file",
            new=AsyncMock(return_value=card_bytes),
        ),
        patch(
            "utils.memory_cards.scan_memory_card_version",
            new=AsyncMock(side_effect=_scan),
        ),
    ):
        yield


def test_first_claim_with_existing_card_asks_before_wiping(
    client, access_token, rom: Rom
):
    """An unadopted container card must never be wiped without an answer."""
    with (
        _streaming(_mc_container_for(rom)),
        patch(
            "handler.streaming.memory_cards.fetch_card", return_value=_gci_card_bytes()
        ),
        patch("handler.streaming.memory_cards.push_card") as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 428
    detail = r.json()["detail"]
    assert detail["code"] == "memory_card_import_required"
    assert detail["outcome"] == "found"
    assert detail["summary"]["game_codes"] == ["GXCE"]
    push.assert_not_called()
    launch.assert_not_called()
    # The prompt is not a session: an abandoned dialog must leave no claim.
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )


def test_unreadable_card_blocks_the_claim(client, access_token, rom: Rom):
    """A transport hiccup must not be read as an empty card."""
    with (
        _streaming(_mc_container_for(rom)),
        patch(
            "handler.streaming.memory_cards.fetch_card",
            side_effect=memory_cards.MemoryCardUnavailable("broker exploded"),
        ),
        patch("handler.streaming.memory_cards.push_card") as push,
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 428
    detail = r.json()["detail"]
    assert detail["outcome"] == "unreadable"
    # The broker host and port must not leak to the client.
    assert "broker exploded" not in detail["reason"]
    assert detail["reason"] == memory_cards.CARD_UNREADABLE_REASON
    push.assert_not_called()
    assert (
        asyncio.run(session_store.get_session(_key_of(_mc_container_for(rom)))) is None
    )


def test_absent_card_claims_without_prompting(client, access_token, rom: Rom):
    """A genuinely empty slot is not a decision, so do not interrupt the user."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch("handler.streaming.memory_cards.fetch_card", return_value=None),
        patch("handler.streaming.memory_cards.push_card", return_value=True),
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    # The absent answer is recorded too, so the probe never runs again here.
    adoption = db_container_adoption_handler.get_adoption(_key_of(container))
    assert adoption is not None and adoption.outcome == "discard"


def test_decided_container_does_not_probe_again(
    client, access_token, admin_user: User, rom: Rom
):
    """After the one-time decision the claim path costs no broker round trip."""
    container = _mc_container_for(rom)
    db_container_adoption_handler.add_adoption(
        container_key=_key_of(container),
        outcome="discard",
        user_id=admin_user.id,
    )
    with (
        _streaming(container),
        patch("handler.streaming.memory_cards.fetch_card") as fetch,
        patch("handler.streaming.memory_cards.push_card", return_value=True),
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    fetch.assert_not_called()


def test_sync_disabled_container_does_not_probe(client, access_token, rom: Rom):
    """Containers without whole-card sync are untouched by any of this."""
    with (
        _streaming(_container_for(rom)),
        patch("handler.streaming.memory_cards.fetch_card") as fetch,
        patch("handler.streaming.commands.launch"),
        patch("handler.streaming.saves.hydrate_saves_to_broker", new=AsyncMock()),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    fetch.assert_not_called()


def test_adopt_stores_the_container_card_as_version_one(
    client, access_token, admin_user: User, rom: Rom
):
    """Adopting must establish a version before hydrate, or the wipe still wins."""
    card_bytes = _gci_card_bytes()
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        _adoption_storage(card_bytes),
        patch("handler.streaming.memory_cards.fetch_card", return_value=card_bytes),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="adopt")
    assert r.status_code == 202
    # The card pushed back down is the adopted one, not a blank.
    assert push.call_args[0][1] == card_bytes
    assert push.call_args[0][1] != memory_cards.EMPTY_CARD
    adoption = db_container_adoption_handler.get_adoption(_key_of(container))
    assert adoption is not None and adoption.outcome == "adopt"
    cards = db_memory_card_handler.get_cards(admin_user.id, "pcsx2")
    assert len(cards) == 1
    assert db_memory_card_handler.get_latest_version(cards[0].id) is not None


def test_discard_wipes_and_records_the_decision(client, access_token, rom: Rom):
    """Choosing fresh must be remembered, or the prompt returns every claim."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch(
            "handler.streaming.memory_cards.fetch_card", return_value=_gci_card_bytes()
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="discard")
    assert r.status_code == 202
    assert push.call_args[0][1] == memory_cards.EMPTY_CARD
    adoption = db_container_adoption_handler.get_adoption(_key_of(container))
    assert adoption is not None and adoption.outcome == "discard"


def test_unreadable_card_with_override_starts_fresh(client, access_token, rom: Rom):
    """The escape hatch: the user accepted the wipe, so proceed to a blank."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch(
            "handler.streaming.memory_cards.fetch_card",
            side_effect=memory_cards.MemoryCardUnavailable("broker exploded"),
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="discard")
    assert r.status_code == 202
    assert push.call_args[0][1] == memory_cards.EMPTY_CARD
    adoption = db_container_adoption_handler.get_adoption(_key_of(container))
    assert adoption is not None and adoption.outcome == "discard"


def test_failed_adopt_aborts_the_claim_without_wiping(
    client, access_token, admin_user: User, rom: Rom
):
    """If the import cannot be stored, hydrate must never get to wipe the card."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch(
            "handler.streaming.memory_cards.fetch_card", return_value=_gci_card_bytes()
        ),
        patch(
            "handler.streaming.memory_cards.store_memory_card_version",
            new=AsyncMock(side_effect=OSError("disk full")),
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="adopt")
    assert r.status_code == 502
    push.assert_not_called()
    launch.assert_not_called()
    # Nothing is recorded, so the next claim asks again instead of wiping.
    assert db_container_adoption_handler.get_adoption(_key_of(container)) is None
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    assert asyncio.run(session_store.get_session(_key_of(container))) is None


def test_adopt_retry_recovers_when_the_version_was_already_stored(
    client, access_token, admin_user: User, rom: Rom
):
    """A claim that stored the version but died before recording the decision
    must not wedge. The retry reads the same container card, dedup refuses a
    second copy, and that is the idempotent case: hydrate would push back the
    very bytes already on the container, so record the decision and continue.
    """
    card_bytes = _gci_card_bytes()
    container = _mc_container_for(rom)
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(
            card.id,
            "My PS2 card [stored].card.zip",
            content_hash_of_bytes(card_bytes),
        )
    )
    with (
        _streaming(container),
        _adoption_storage(card_bytes),
        patch("handler.streaming.memory_cards.fetch_card", return_value=card_bytes),
        patch("handler.streaming.memory_cards.push_card", return_value=True),
        patch("handler.streaming.commands.launch"),
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="adopt")
    assert r.status_code == 202
    adoption = db_container_adoption_handler.get_adoption(_key_of(container))
    assert adoption is not None and adoption.outcome == "adopt"
    # Dedup still holds: the retry adds no second copy of the same content.
    assert len(db_memory_card_handler.get_versions(card.id)) == 1


def test_adopt_aborts_when_dedup_matches_an_older_version(
    client, access_token, admin_user: User, rom: Rom
):
    """A match against a version that is NOT the latest still has to abort:
    hydrate would push the newer version over the card asked to be kept."""
    card_bytes = _gci_card_bytes()
    container = _mc_container_for(rom)
    card = _make_card(admin_user)
    older = _card_version(
        card.id,
        "My PS2 card [old].card.zip",
        content_hash_of_bytes(card_bytes),
    )
    older.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = _card_version(card.id, "My PS2 card [newer].card.zip", "newer-hash")
    newer.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db_memory_card_handler.add_version(older)
    db_memory_card_handler.add_version(newer)
    with (
        _streaming(container),
        _adoption_storage(card_bytes),
        patch("handler.streaming.memory_cards.fetch_card", return_value=card_bytes),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(
            client, access_token, rom.id, memory_card_id=card.id, card_import="adopt"
        )
    assert r.status_code == 502
    push.assert_not_called()
    launch.assert_not_called()
    assert db_container_adoption_handler.get_adoption(_key_of(container)) is None
    assert asyncio.run(session_store.get_session(_key_of(container))) is None


def test_adopt_with_unreadable_card_aborts_without_recording(
    client, access_token, admin_user: User, rom: Rom
):
    """ "Keep this card" on a card that cannot be read must never wipe it: only
    an explicit discard may override an unreadable card."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch(
            "handler.streaming.memory_cards.fetch_card",
            side_effect=memory_cards.MemoryCardUnavailable("broker exploded"),
        ),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="adopt")
    assert r.status_code == 502
    push.assert_not_called()
    launch.assert_not_called()
    # No decision recorded, so the next claim asks again instead of wiping.
    assert db_container_adoption_handler.get_adoption(_key_of(container)) is None
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    assert asyncio.run(session_store.get_session(_key_of(container))) is None


def test_adopt_with_absent_card_aborts_without_recording(
    client, access_token, admin_user: User, rom: Rom
):
    """The card vanished between the prompt and the answer, so the import the
    user asked for cannot happen. Say so instead of starting on a blank."""
    container = _mc_container_for(rom)
    with (
        _streaming(container),
        patch("handler.streaming.memory_cards.fetch_card", return_value=None),
        patch("handler.streaming.memory_cards.push_card", return_value=True) as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(client, access_token, rom.id, card_import="adopt")
    assert r.status_code == 502
    push.assert_not_called()
    launch.assert_not_called()
    assert db_container_adoption_handler.get_adoption(_key_of(container)) is None
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    assert asyncio.run(session_store.get_session(_key_of(container))) is None


def test_occupied_undecided_container_returns_409_not_428(
    client, viewer_access_token, admin_user: User, rom: Rom
):
    """The probe belongs to the claim winner: a second player must not be shown
    a prompt describing the card of whoever is playing right now."""
    container = _mc_container_for(rom)
    key = session_store.session_redis_key(_key_of(container))
    asyncio.run(
        async_cache.set(
            key,
            json.dumps(
                {
                    "rom_id": rom.id,
                    "rom_name": rom.name,
                    "platform": rom.platform_slug,
                    "claimed_at": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "user_id": admin_user.id,
                    "memory_card_id": None,
                }
            ),
        )
    )
    with (
        _streaming(container),
        patch(
            "handler.streaming.memory_cards.fetch_card", return_value=_gci_card_bytes()
        ) as fetch,
        patch("handler.streaming.memory_cards.push_card") as push,
        patch("handler.streaming.commands.launch") as launch,
        _spawns_nothing(),
    ):
        r = _mc_claim(client, viewer_access_token, rom.id)
    assert r.status_code == 409
    fetch.assert_not_called()
    push.assert_not_called()
    launch.assert_not_called()


def _mc_webstation_for(rom: Rom):
    """A webstation container on whole-card sync, serving ps2 through pcsx2."""
    return {**_mc_container_for(rom), "protocol": "webstation", "subfolder": "/stream"}


def test_memory_card_route_names_the_emulator_on_a_webstation_container(rom: Rom):
    """One webstation container hosts several emulators, so the card it serves
    has to be named; an emulator with a platform-gated card (Dolphin: GC, not
    Wii) also needs the platform. The per-emulator brokers serve the one card
    they have and need neither."""
    with _streaming(_mc_webstation_for(rom)):
        nested = _first_container(rom.platform_slug)
    with _streaming(_mc_container_for(rom)):
        flat = _first_container(rom.platform_slug)
    assert (
        nested.memory_card_route()
        == f"/stream/api/session/memory-card?emulator=pcsx2&platform={rom.platform_slug}"
    )
    assert flat.memory_card_route() == "/memory-card"


def test_webstation_claim_hydrates_the_card_and_the_states(
    client, access_token, rom: Rom
):
    """A webstation container takes both hydrates: the card carries the game's
    own saves, the archive carries the state the last session ended on."""
    with _streaming(_mc_webstation_for(rom)):
        with (
            patch("handler.streaming.webstation.activate", return_value={}),
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ) as card,
            patch(
                "handler.streaming.states.hydrate_states_to_broker", new=AsyncMock()
            ) as states,
            patch(
                "handler.streaming.saves.hydrate_saves_to_broker", new=AsyncMock()
            ) as legacy,
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    card.assert_awaited_once()
    # The state hydrate is spawned rather than awaited inline, so the claim can
    # return while the push is still in flight.
    states.assert_called_once()
    legacy.assert_not_called()


def test_webstation_claim_tells_the_broker_the_card_is_synced(
    client, access_token, rom: Rom
):
    """Without the flag the broker would restore and dump the card inside the
    save archive too, fighting the image the card routes just laid down."""
    with _streaming(_mc_webstation_for(rom)):
        with (
            patch("handler.streaming.webstation.activate", return_value={}) as activate,
            patch("handler.streaming.memory_cards.fetch_card", return_value=None),
            patch(
                "handler.streaming.memory_cards.hydrate_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            patch("handler.streaming.states.hydrate_states_to_broker", new=AsyncMock()),
            _spawns_nothing(),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 202
    assert activate.call_args.kwargs["memory_card_synced"] is True


def test_concurrent_adopts_record_one_decision(admin_user: User, rom: Rom):
    """The unique constraint decides, so the loser must not 500."""
    key = _key_of(_mc_container_for(rom))
    first = db_container_adoption_handler.add_adoption(
        container_key=key, outcome="adopt", user_id=admin_user.id
    )
    second = db_container_adoption_handler.add_adoption(
        container_key=key, outcome="discard", user_id=admin_user.id
    )
    assert first is not None
    assert second is None
    adoption = db_container_adoption_handler.get_adoption(key)
    assert adoption is not None
    assert adoption.outcome == "adopt"


# ── Playtime ──────────────────────────────────────────────────────────────────


def test_record_play_session_stores_duration(admin_user: User, rom: Rom):
    """A finished streaming session is recorded as playtime and updates the
    ROM's last_played, keyed off the stored claim timestamp."""
    start = datetime.now(timezone.utc) - timedelta(minutes=10)
    session = {
        "user_id": admin_user.id,
        "rom_id": rom.id,
        "claimed_at": start.isoformat(),
    }
    asyncio.run(lifecycle.record_play_session(session))

    total_ms = db_play_session_handler.get_total_play_time(admin_user.id, rom.id)
    # ~10 minutes, allow slack for wall-clock drift between claim and record.
    assert 9 * 60_000 <= total_ms <= 11 * 60_000
    rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=admin_user.id)
    assert rom_user is not None and rom_user.last_played is not None


def test_record_play_session_skips_accidental_short_session(admin_user: User, rom: Rom):
    """A claim released almost immediately is noise, not playtime."""
    session = {
        "user_id": admin_user.id,
        "rom_id": rom.id,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    asyncio.run(lifecycle.record_play_session(session))
    assert db_play_session_handler.get_total_play_time(admin_user.id, rom.id) == 0


def test_record_play_session_ignores_malformed_session(admin_user: User, rom: Rom):
    """Missing rom_id / claimed_at must be a no-op, never an error."""
    asyncio.run(lifecycle.record_play_session({"user_id": admin_user.id}))
    asyncio.run(
        lifecycle.record_play_session(
            {"user_id": admin_user.id, "rom_id": rom.id, "claimed_at": "not-a-date"}
        )
    )
    assert db_play_session_handler.get_total_play_time(admin_user.id, rom.id) == 0


# ── Activity board ────────────────────────────────────────────────────────────


def _activity_entry(container: dict[str, Any], user: User):
    return asyncio.run(activity_handler.get_active(user.id, _key_of(container)))


def test_a_claimed_session_shows_on_the_activity_board(
    client, access_token, admin_user: User, rom: Rom
):
    """A streaming session is a play session like any other, so it joins the
    devices on /activity rather than being visible only to admins."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)

    entry = _activity_entry(container, admin_user)
    assert entry is not None
    assert entry["rom_id"] == rom.id
    assert entry["device_id"] == _key_of(container)
    assert entry["device_type"] == "streaming"


def test_releasing_a_session_takes_it_off_the_activity_board(
    client, access_token, admin_user: User, rom: Rom
):
    """The board is socket-driven, so an entry left behind sits on an open
    board until its TTL runs out."""
    container = _container_for(rom)
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        with _stub_stop():
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert _activity_entry(container, admin_user) is None


def test_a_broken_activity_board_does_not_fail_the_launch(
    client, access_token, admin_user: User, rom: Rom
):
    """The board is a view of the session, never a reason to refuse one."""
    container = _container_for(rom)
    with _streaming(container):
        with patch.object(
            activity_handler, "publish_active", side_effect=RuntimeError("redis gone")
        ):
            r = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 202
    assert _session_raw(container) is not None
    assert _activity_entry(container, admin_user) is None


def test_summarize_memory_card_reports_files_and_game_codes():
    """The dialog names games, so the summary lifts gamecodes from .gci names."""
    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("01-GXCE-CustomRobo-BattleRevolution.gci", b"x" * 100)
        zf.writestr("01-GALE-SuperSmashBros.gci", b"y" * 50)
    summary = memory_cards.summarize_card(buf.getvalue())
    assert summary["file_count"] == 2
    assert summary["total_bytes"] == 150
    assert summary["game_codes"] == ["GALE", "GXCE"]


def test_summarize_memory_card_handles_unparsable_content():
    """A card we cannot parse describes nothing, and never raises into the claim."""
    summary = memory_cards.summarize_card(b"not a zip")
    assert summary["file_count"] == 0
    assert summary["total_bytes"] == 0
    assert summary["game_codes"] == []


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/streaming/sessions", {"rom_id": 1}),
        ("post", "/api/streaming/sessions/ps2/save-and-exit", {}),
        ("post", "/api/streaming/sessions/ps2/heartbeat", {}),
        ("post", "/api/streaming/sessions/ps2/volume", {"level": 50}),
        ("post", "/api/streaming/sessions/ps2/mute", {"mute": True}),
        ("post", "/api/streaming/sessions/ps2/save-state", {"slot": 1}),
        ("post", "/api/streaming/sessions/ps2/load-state", {"slot": 1}),
        ("delete", "/api/streaming/sessions/ps2", None),
        ("delete", "/api/streaming/sessions", None),
    ],
)
def test_kiosk_mode_cannot_mutate_sessions(client, method, path, body):
    """KIOSK_MODE hands anonymous visitors READ_SCOPES, which must not suffice.

    Every kiosk visitor resolves to the same synthetic user (id=-1), so session
    ownership cannot separate them -- without a write scope on these routes an
    anonymous visitor could claim sessions and overwrite others' save states.
    """
    with patch("handler.auth.hybrid_auth.KIOSK_MODE", True):
        kwargs = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kwargs).status_code == 403


def test_kiosk_mode_can_still_read_config(client):
    """The read side of streaming stays open to kiosk visitors."""
    with patch("handler.auth.hybrid_auth.KIOSK_MODE", True), _streaming():
        assert client.get("/api/streaming/config").status_code == 200


# ── RetroArch core on activate ──────────────────────────────────────────────


def _ra_claim(client, token, rom: Rom, value, reply: dict[str, Any]):
    """Claim `rom` on a webstation container serving its platform as `value`,
    with the broker transport answering `reply`. Returns the activate body,
    what the launch pushed, and the exit_session mock. Stubs the transport
    rather than `activate`, like `_activate_body`: the body is the point."""
    with _streaming(_webstation(platforms={rom.platform_slug: value})):
        with (
            _pushes() as sent,
            patch("handler.streaming.broker.request", return_value=reply) as request,
            patch("handler.streaming.webstation.exit_session") as exit_session,
            _spawns_nothing(),
        ):
            client.post(
                "/api/streaming/sessions",
                json={"rom_id": rom.id},
                headers=_auth(token),
            )
    activate = next(
        c for c in request.call_args_list if c.args[1].endswith("/activate")
    )
    return activate.kwargs["body"], sent, exit_session


_BSNES_REPLY: dict[str, Any] = {
    "url": "/room/x",
    "core": "bsnes",
    "core_tier": "untested",
}


def test_the_activate_body_carries_a_configured_core(client, access_token, rom: Rom):
    body, _, _ = _ra_claim(client, access_token, rom, "retroarch:bsnes", _BSNES_REPLY)
    assert body["rom"]["core"] == "bsnes"
    assert "experimental_cores" not in body["rom"]


def test_status_warns_a_tab_that_missed_launch_ready_of_its_core(
    client, access_token, rom: Rom
):
    platforms = {rom.platform_slug: "retroarch:bsnes"}
    with _streaming(_webstation(platforms=platforms)):
        with (
            _pushes(),
            patch("handler.streaming.broker.request", return_value=_BSNES_REPLY),
            _spawns_nothing(),
        ):
            client.post(
                "/api/streaming/sessions",
                json={"rom_id": rom.id},
                headers=_auth(access_token),
            )
            r = client.get(
                f"/api/streaming/sessions/{rom.platform_slug}/status",
                headers=_auth(access_token),
            )
    assert r.json()["core"] == "bsnes"
    assert r.json()["core_tier"] == "untested"


def test_the_activate_body_carries_the_opt_in(client, access_token, rom: Rom):
    value = {"emulator": "retroarch", "core": "bsnes", "experimental_cores": True}
    body, _, _ = _ra_claim(client, access_token, rom, value, _BSNES_REPLY)
    assert body["rom"]["experimental_cores"] is True


def test_no_core_leaves_the_activate_body_unchanged(client, access_token, rom: Rom):
    """An opt-in alone means nothing without a core, so it stays home too."""
    body, _, exit_session = _ra_claim(
        client,
        access_token,
        rom,
        {"emulator": "retroarch", "experimental_cores": True},
        {"url": "/room/x"},
    )
    assert "core" not in body["rom"]
    assert "experimental_cores" not in body["rom"]
    exit_session.assert_not_called()


def test_an_older_broker_that_drops_the_core_is_exited_asking_for_no_save(
    client, access_token, rom: Rom
):
    """Pydantic drops the unknown field and the broker boots
    its default, which would file this session's saves under the wrong core."""
    _, sent, exit_session = _ra_claim(
        client, access_token, rom, "retroarch:bsnes", {"url": "/room/x"}
    )
    exit_session.assert_called_once()
    assert exit_session.call_args.args[1] == 0
    assert exit_session.call_args.kwargs == {"save": False}
    failed = next(p for event, p in sent if event == "streaming:launch-failed")
    assert "doesn't support `core:`" in failed["detail"]
    assert f"the {rom.platform_slug} platform" in failed["detail"]
    assert _launch_ready(sent) == {}


def test_a_wrong_core_is_exited_again_when_the_first_exit_fails():
    """The broker refuses every activate while that game runs, so one lost exit
    would wedge the container once the claim is released."""
    with (
        patch("handler.streaming.broker.request", return_value={"url": "/room/x"}),
        patch(
            "handler.streaming.webstation.exit_session",
            side_effect=[None, {"state_saved": False}],
        ) as exit_session,
        pytest.raises(HTTPException),
    ):
        webstation.activate(
            _snes("retroarch:bsnes"),
            session_id="s",
            user=MagicMock(id=1, username="u"),
            emulator="retroarch",
            rom={"id": 1, "name": "Game", "platform": "snes"},
        )
    assert exit_session.call_count == 2


def test_a_broker_that_drops_the_core_logs_no_traceback(
    client, access_token, rom: Rom, caplog
):
    """The 502 is a config message for the operator, not a crash."""
    _warnings_of(
        caplog,
        lambda: _ra_claim(
            client, access_token, rom, "retroarch:bsnes", {"url": "/room/x"}
        ),
    )
    failed = [r for r in caplog.records if r.getMessage().startswith("launch failed")]
    assert failed
    assert all(r.exc_info is None for r in failed)


def test_a_broker_that_echoes_the_core_launches(client, access_token, rom: Rom):
    _, sent, exit_session = _ra_claim(
        client, access_token, rom, "retroarch:bsnes", _BSNES_REPLY
    )
    exit_session.assert_not_called()
    assert _launch_ready(sent) != {}


def test_launch_ready_names_the_core_and_its_tier(client, access_token, rom: Rom):
    _, sent, _ = _ra_claim(client, access_token, rom, "retroarch:bsnes", _BSNES_REPLY)
    ready = _launch_ready(sent)
    assert (ready["core"], ready["core_tier"]) == ("bsnes", "untested")


def test_launch_ready_has_no_tier_without_a_core(client, access_token, rom: Rom):
    """A new broker reports the default's tier on every RetroArch launch; with
    no core configured there is nothing to warn about."""
    reply = {"url": "/room/x", "core": "snes9x", "core_tier": "default"}
    _, sent, _ = _ra_claim(client, access_token, rom, "retroarch", reply)
    ready = _launch_ready(sent)
    assert (ready["core"], ready["core_tier"]) == (None, None)


def test_a_malformed_core_tier_still_reaches_launch_ready(
    client, access_token, rom: Rom
):
    """The session is already running, so a bad tier must not cost the player
    the room URL."""
    reply = {**_BSNES_REPLY, "core_tier": 3}
    _, sent, _ = _ra_claim(client, access_token, rom, "retroarch:bsnes", reply)
    ready = _launch_ready(sent)
    assert (ready["core"], ready["core_tier"]) == ("bsnes", None)


def test_a_desktop_on_a_container_with_a_core_boots_no_core(client, access_token):
    """The desktop runs on the container's first platform record, whose core
    it never boots, so the broker's missing echo is not a skew."""
    container = _webstation(platforms={"snes": "retroarch:bsnes"})
    with _streaming(container):
        with (
            patch(
                "handler.streaming.broker.request", return_value={"url": "/room/x"}
            ) as request,
            patch("handler.streaming.webstation.exit_session") as exit_session,
        ):
            response = client.post(
                "/api/streaming/desktop",
                json={"container": _key_of(container)},
                headers=_auth(access_token),
            )
    assert response.status_code == 200
    exit_session.assert_not_called()
    activate = next(
        c for c in request.call_args_list if c.args[1].endswith("/activate")
    )
    assert "rom" not in activate.kwargs["body"]


# ── multiplayer flag ─────────────────────────────────────────────────────────


def _ws_for(rom: Rom):
    """A webstation container serving this rom's platform, since only the
    webstation broker mints viewer seats."""
    return _webstation(platforms={rom.platform_slug: "pcsx2"})


def _claim_multiplayer(client, token, rom_id, multiplayer=True):
    """Claim with multiplayer requested and whichever broker the container
    speaks stubbed out."""
    with (
        patch("handler.streaming.commands.launch"),
        patch("handler.streaming.webstation.activate", return_value={"url": "/room/x"}),
    ):
        return client.post(
            "/api/streaming/sessions",
            json={"rom_id": rom_id, "multiplayer": multiplayer},
            headers=_auth(token),
        )


def test_a_multiplayer_claim_is_recorded_on_the_session(client, access_token, rom: Rom):
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        raw = _session_raw(container)

    assert json.loads(raw)["multiplayer"] is True


def test_the_activate_body_carries_the_multiplayer_flag(client, access_token, rom: Rom):
    """The broker gates its comms surface on this field, so stub the transport
    rather than the activate helper: the body itself is what matters."""
    with _streaming(_ws_for(rom)):
        with patch(
            "handler.streaming.broker.request", return_value={"url": "/room/x"}
        ) as request:
            client.post(
                "/api/streaming/sessions",
                json={"rom_id": rom.id, "multiplayer": True},
                headers=_auth(access_token),
            )

    assert request.call_args.kwargs["body"]["multiplayer"] is True


def _activate_body(client, token, rom: Rom) -> dict[str, Any]:
    """Claim through the webstation protocol and return the activate body."""
    with _streaming(_ws_for(rom)):
        with patch(
            "handler.streaming.broker.request", return_value={"url": "/room/x"}
        ) as request:
            client.post(
                "/api/streaming/sessions",
                json={"rom_id": rom.id},
                headers=_auth(token),
            )
    return cast(dict[str, Any], request.call_args.kwargs["body"])


def test_the_activate_body_carries_the_rom_language(client, access_token, rom: Rom):
    """ScummVM registers one target per language detected in a game folder and
    the target is what boots, so a multilingual game needs this to start in the
    language the ROM is recorded as."""
    db_rom_handler.update_rom(rom.id, {"languages": ["French"]})

    assert _activate_body(client, access_token, rom)["rom"]["language"] == "fr"


def test_the_rom_language_is_reduced_to_an_iso_code(client, access_token, rom: Rom):
    """Filename parsing stores names ("French"), metadata providers store
    shortcodes ("fr"); brokers only ever see the ISO-639-1 code."""
    db_rom_handler.update_rom(rom.id, {"languages": ["fr"]})

    assert _activate_body(client, access_token, rom)["rom"]["language"] == "fr"


def test_a_provider_only_language_is_reduced_too(client, access_token, rom: Rom):
    """The languages only a provider reports ("Czech") have no filename
    shortcode, so the broker would otherwise get nothing for them."""
    db_rom_handler.update_rom(rom.id, {"languages": ["Czech"]})

    assert _activate_body(client, access_token, rom)["rom"]["language"] == "cs"


def test_an_unknown_rom_language_is_sent_as_none(client, access_token, rom: Rom):
    """A value RomM cannot reduce leaves the broker on its own default rather
    than failing the launch."""
    db_rom_handler.update_rom(rom.id, {"languages": ["Klingon"]})

    assert _activate_body(client, access_token, rom)["rom"]["language"] is None


def test_a_rom_without_a_language_sends_none(client, access_token, rom: Rom):
    assert _activate_body(client, access_token, rom)["rom"]["language"] is None


def test_the_activate_body_carries_the_users_interface_language(
    client, access_token, admin_user: User, rom: Rom
):
    """RomM rarely knows a game's own language, and a multilingual folder is
    exactly where it usually does not, so the player's locale travels with it
    as the broker's fallback."""
    db_user_handler.update_user(admin_user.id, {"ui_settings": {"locale": "fr_FR"}})

    assert _activate_body(client, access_token, rom)["gui_language"] == "fr-fr"


def test_the_interface_language_keeps_its_region(
    client, access_token, admin_user: User, rom: Rom
):
    """Brazilian and European Portuguese are different games to an emulator
    that ships both, so the region travels and the broker decides what to make
    of it."""
    db_user_handler.update_user(admin_user.id, {"ui_settings": {"locale": "pt_BR"}})

    assert _activate_body(client, access_token, rom)["gui_language"] == "pt-br"


def test_the_interface_language_is_left_out_when_unset(client, access_token, rom: Rom):
    """No locale means the broker keeps whatever the container is configured
    with, rather than being handed an empty one to pin."""
    assert "gui_language" not in _activate_body(client, access_token, rom)


def test_the_interface_language_sits_beside_the_rom_not_inside_it(
    client, access_token, admin_user: User, rom: Rom
):
    """It describes the player, so a launch with no rom still carries it."""
    db_user_handler.update_user(admin_user.id, {"ui_settings": {"locale": "fr_FR"}})
    body = _activate_body(client, access_token, rom)

    assert "gui_language" not in body["rom"]


def test_a_claim_on_a_container_that_cannot_seat_a_joiner_stays_solo(
    client, access_token, rom: Rom
):
    """Only the webstation broker mints viewer seats, so the switch must not
    open a session every Join would 409 on."""
    container = {"host": "http://192.168.1.10:3000", "platform": rom.platform_slug}
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        raw = _session_raw(container)

    assert json.loads(raw)["multiplayer"] is False


def test_a_claim_is_solo_unless_asked_otherwise(client, access_token, rom: Rom):
    container = {"host": "http://192.168.1.10:3000", "platform": rom.platform_slug}
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        raw = _session_raw(container)

    assert json.loads(raw)["multiplayer"] is False


# ── joinable sessions ────────────────────────────────────────────────────────


def _joinable(client, token, rom_id=None):
    params = {} if rom_id is None else {"rom_id": rom_id}
    return client.get(
        "/api/streaming/sessions/joinable", params=params, headers=_auth(token)
    )


def test_joinable_lists_someone_elses_multiplayer_session(
    client, access_token, viewer_access_token, rom: Rom
):
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert [s["rom_id"] for s in body["sessions"]] == [rom.id]


def test_joinable_lists_sessions_for_different_roms(
    client, access_token, viewer_access_token, admin_user: User, rom: Rom
):
    """A second session's rom_id must not be filtered against the first's."""
    other_platform = make_platform("other_platform_slug", name="other_platform")
    other_rom = make_rom(other_platform, "other_rom")
    db_rom_handler.add_rom_user(rom_id=other_rom.id, user_id=admin_user.id)

    container_a = _ws_for(rom)
    container_b = {
        **_ws_for(other_rom),
        "host": "http://192.168.1.11:3000",
        "broker_host": "http://192.168.1.11:8000",
    }
    with _streaming(container_a, container_b):
        _claim_multiplayer(client, access_token, rom.id)
        _claim_multiplayer(client, access_token, other_rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert {s["rom_id"] for s in body["sessions"]} == {rom.id, other_rom.id}


def test_joinable_keeps_the_containers_own_label(
    client, access_token, viewer_access_token
):
    """`_platform_row` computes a per-platform emulator label for /config,
    but the listing wants the container's own configured identity, the same
    as GET /sessions already does."""
    rom = _rom_on("ps2")
    with _streaming(_webstation(label="My Box")):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert body["sessions"][0]["label"] == "My Box"


def test_joinable_carries_the_rom_cover_and_platform(
    client, access_token, viewer_access_token, rom: Rom
):
    """The home page draws a tile per session straight from this listing."""
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        session = _joinable(client, viewer_access_token).json()["sessions"][0]

    assert session["platform_id"] == rom.platform_id
    assert session["platform_display_name"] == rom.platform_display_name
    assert session["path_cover_small"] == rom.path_cover_small
    assert session["path_cover_large"] == rom.path_cover_large
    assert session["url_cover"] == rom.url_cover
    assert session["claimed_at"]


def test_joinable_hides_a_solo_session(
    client, access_token, viewer_access_token, rom: Rom
):
    container = {"host": "http://192.168.1.10:3000", "platform": rom.platform_slug}
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert body["sessions"] == []


def test_joinable_skips_the_rom_lookup_for_a_session_nobody_may_join(
    client, access_token, viewer_access_token, rom: Rom
):
    """Home polls this listing, and most live sessions are solo."""
    container = {"host": "http://192.168.1.10:3000", "platform": rom.platform_slug}
    with _streaming(container):
        _claim_ok(client, access_token, rom.id)
        with patch("handler.streaming.access.session_rom") as lookup:
            _joinable(client, viewer_access_token)

    lookup.assert_not_called()


def test_joinable_hides_a_session_nobody_could_join(
    client, access_token, viewer_access_token, rom: Rom
):
    """A container with no join route never reaches the listing, so no Join
    button is offered for a session that cannot seat anyone."""
    with _streaming(
        {"host": "http://192.168.1.10:3000", "platform": rom.platform_slug}
    ):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert body["sessions"] == []


def test_joinable_hides_your_own_session(client, access_token, rom: Rom):
    """Nobody needs a Join button for the game they are already hosting."""
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, access_token).json()

    assert body["sessions"] == []


def test_joinable_filters_by_rom(client, access_token, viewer_access_token, rom: Rom):
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token, rom_id=rom.id + 1).json()

    assert body["sessions"] == []


def test_joinable_requires_auth(client):
    assert client.get("/api/streaming/sessions/joinable").status_code == 401


def test_joinable_hides_a_session_whose_rom_is_hidden(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """The listing leaks rom_name and host_username, so a ROM the caller
    cannot see must not appear in it."""
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert body["sessions"] == []


def test_joinable_hides_a_session_on_a_hidden_platform(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom, platform
):
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()

    assert body["sessions"] == []


# ── joining a session ─────────────────────────────────────────────────────────


def _join(client, token, platform, container=None):
    params = {} if container is None else {"container": container}
    return client.post(
        f"/api/streaming/sessions/{platform}/join",
        params=params,
        headers=_auth(token),
    )


def test_joining_a_multiplayer_session_returns_its_room_url(
    client, access_token, viewer_access_token, rom: Rom
):
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch(
            "handler.streaming.webstation.join",
            return_value={"url": "/webstation/?token=abc"},
        ):
            response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 200
    assert response.json()["host"] == "http://192.168.1.10:3000/webstation/?token=abc"


def test_joining_ignores_a_room_url_that_leaves_the_container(
    client, access_token, viewer_access_token, rom: Rom
):
    """Same guard as a claim: a joiner's iframe stays on the configured host."""
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch(
            "handler.streaming.webstation.join",
            return_value={"url": "https://evil.example/room"},
        ):
            response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.json()["host"] == "http://192.168.1.10:3000"


def test_joining_a_hidden_rom_is_404_masked(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """Joining streams the host's ROM, so it needs the same visibility policy
    the claim route enforces; masked as the not-found so nothing leaks."""
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch("handler.streaming.webstation.join") as join_broker:
            response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 404
    join_broker.assert_not_called()


def test_joining_a_rom_on_a_hidden_platform_is_404_masked(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom, platform
):
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch("handler.streaming.webstation.join") as join_broker:
            response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 404
    join_broker.assert_not_called()


def _ws_pool_member(rom: Rom, index: int, **overrides) -> dict[str, Any]:
    """One member of a pool of webstation containers, the broker a joiner needs,
    on a distinct host so the room URL says which member answered."""
    return cast(
        dict[str, Any],
        _webstation(
            **{
                "host": f"http://192.168.1.1{index}:3000",
                "broker_host": f"http://192.168.1.1{index}:8000",
                "platforms": {rom.platform_slug: "pcsx2"},
                **overrides,
            }
        ),
    )


def _joined_room(url: str = "/webstation/?token=abc"):
    return patch("handler.streaming.webstation.join", return_value={"url": url})


def test_joining_walks_past_a_session_whose_rom_is_hidden(
    client,
    access_token,
    editor_access_token,
    viewer_access_token,
    viewer_user: User,
    rom: Rom,
    second_rom: Rom,
):
    """A hidden ROM earlier in the pool is not the caller's answer, so it must
    not mask the joinable session behind it."""
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    with _streaming(_ws_pool_member(rom, 0), _ws_pool_member(rom, 1)):
        _claim_multiplayer(client, access_token, rom.id)
        _claim_multiplayer(client, editor_access_token, second_rom.id)
        with _joined_room():
            r = _join(client, viewer_access_token, rom.platform_slug)

    assert r.status_code == 200
    assert r.json()["rom_id"] == second_rom.id


def test_joining_walks_past_the_callers_own_session(
    client, access_token, viewer_access_token, rom: Rom, second_rom: Rom
):
    """Joining is for somebody else's game: the caller's own session is the one
    they already hold, and the listing leaves it out for the same reason."""
    with _streaming(_ws_pool_member(rom, 0), _ws_pool_member(rom, 1)):
        _claim_multiplayer(client, viewer_access_token, rom.id)
        _claim_multiplayer(client, access_token, second_rom.id)
        with _joined_room():
            r = _join(client, viewer_access_token, rom.platform_slug)

    assert r.status_code == 200
    assert r.json()["rom_id"] == second_rom.id


def test_joining_walks_past_a_session_on_another_platform(
    client,
    access_token,
    editor_access_token,
    viewer_access_token,
    rom: Rom,
    second_rom: Rom,
):
    """A container serves several platforms and holds one session, so a member
    busy with another platform is not this platform's session to join."""
    member = _ws_pool_member(
        rom, 0, platforms={rom.platform_slug: "pcsx2", "ngc": "dolphin"}
    )
    with _streaming(member, _ws_pool_member(rom, 1)):
        _claim_multiplayer(client, access_token, rom.id)
        key = session_store.session_redis_key(_key_of(member))
        raw = asyncio.run(async_cache.get(key))
        assert raw is not None
        session = json.loads(raw)
        session["platform"] = "ngc"
        asyncio.run(async_cache.set(key, json.dumps(session)))
        _claim_multiplayer(client, editor_access_token, second_rom.id)
        with _joined_room():
            r = _join(client, viewer_access_token, rom.platform_slug)

    assert r.status_code == 200
    assert r.json()["rom_id"] == second_rom.id


def test_joining_a_named_container_busy_with_another_platform_is_a_404(
    client, access_token, viewer_access_token, rom: Rom
):
    """Naming the container skips the walk, not its platform check: the game there
    now may be another platform's, never the one the caller asked to join."""
    member = _ws_pool_member(
        rom, 0, platforms={rom.platform_slug: "pcsx2", "ngc": "dolphin"}
    )
    with _streaming(member):
        _claim_multiplayer(client, access_token, rom.id)
        key = session_store.session_redis_key(_key_of(member))
        raw = asyncio.run(async_cache.get(key))
        assert raw is not None
        session = json.loads(raw)
        session["platform"] = "ngc"
        asyncio.run(async_cache.set(key, json.dumps(session)))
        with _joined_room():
            r = _join(
                client,
                viewer_access_token,
                rom.platform_slug,
                container=_key_of(member),
            )

    assert r.status_code == 404


def test_joining_a_solo_session_finds_nothing_to_join(
    client, access_token, viewer_access_token, rom: Rom
):
    """The scan skips solo sessions outright, so there is nothing to refuse."""
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id, multiplayer=False)
        response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 404


def test_joining_a_named_solo_container_is_refused(
    client, access_token, viewer_access_token, rom: Rom
):
    """Naming the container skips the scan, so the refusal is explicit."""
    container = _ws_for(rom)
    with _streaming(container):
        _claim_multiplayer(client, access_token, rom.id, multiplayer=False)
        response = _join(
            client, viewer_access_token, rom.platform_slug, container=_key_of(container)
        )

    assert response.status_code == 403


def test_joining_when_nothing_is_running_is_a_404(
    client, viewer_access_token, rom: Rom
):
    with _streaming(_ws_for(rom)):
        response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 404


def test_a_joiner_cannot_drive_the_session(
    client, access_token, viewer_access_token, rom: Rom
):
    """Joining hands out a room URL, never control of the container."""
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch(
            "handler.streaming.webstation.join",
            return_value={"url": "/webstation/?token=abc"},
        ):
            assert (
                _join(client, viewer_access_token, rom.platform_slug).status_code == 200
            )
        response = _volume(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 403


def test_a_refused_mint_is_a_502(client, access_token, viewer_access_token, rom: Rom):
    """The broker answering with no URL must not read as a successful join."""
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch("handler.streaming.webstation.join", return_value=None):
            response = _join(client, viewer_access_token, rom.platform_slug)

    assert response.status_code == 502


def test_joining_requires_auth(client, rom: Rom):
    with _streaming(_ws_for(rom)):
        r = client.post(f"/api/streaming/sessions/{rom.platform_slug}/join")
    assert r.status_code == 401


# ── Container expansion ───────────────────────────────────────────────────────


def _expand(entry: dict[str, Any]) -> list[ResolvedContainer]:
    """The records the resolver builds for one raw config entry."""
    with _streaming(entry):
        return list(resolve_containers())


def test_expand_platform_block_overrides_container_defaults():
    """A platform block is the per-platform default, the container is the
    fallback, so one webstation can label each emulator for itself."""
    expanded = _expand(
        {
            "host": "http://box:3010",
            "label": "Emulation station",
            "memory_card_sync": False,
            "platforms": {
                "ps2": {
                    "emulator": "pcsx2",
                    "label": "PCSX2",
                    "memory_card_sync": True,
                },
                "wii": {"emulator": "dolphin"},
                "snes": "retroarch",
            },
        }
    )

    by_platform = {row.platform: row for row in expanded}
    assert by_platform["ps2"].emulator == "pcsx2"
    assert by_platform["ps2"].label == "PCSX2"
    assert by_platform["ps2"].memory_card_sync is True
    # A block that omits a key falls through to the container.
    assert by_platform["wii"].emulator == "dolphin"
    assert by_platform["wii"].label == "Dolphin"
    assert by_platform["wii"].memory_card_sync is False
    # The bare string form inherits everything but the label, which the
    # emulator names.
    assert by_platform["snes"].emulator == "retroarch"
    assert by_platform["snes"].label == "RA Snes9x"
    assert by_platform["snes"].memory_card_sync is False


def test_expand_platform_block_without_an_emulator_is_skipped():
    """The emulator names the state and card namespace, so a block that omits
    it is dropped rather than guessed, and its siblings still expand."""
    expanded = _expand(
        {
            "host": "http://box:3010",
            "platforms": {"ps2": {"label": "PCSX2"}, "snes": "retroarch"},
        }
    )

    assert [row.platform for row in expanded] == ["snes"]


def test_expand_platform_block_ignores_an_unknown_option():
    expanded = _expand(
        {
            "host": "http://box:3010",
            "platforms": {"ps2": {"emulator": "pcsx2", "nonsense": 1}},
        }
    )

    assert [row.platform for row in expanded] == ["ps2"]


def test_expand_platform_value_that_is_neither_name_nor_block_is_skipped():
    expanded = _expand(
        {"host": "http://box:3010", "platforms": {"ps2": 42, "snes": "retroarch"}}
    )

    assert [row.platform for row in expanded] == ["snes"]


# ── Broker host derivation ────────────────────────────────────────────────────


def _broker_host_of(entry: dict[str, Any]) -> str | None:
    return _derive_broker_host(
        entry, protocol_for(entry.get("protocol"), entry.get("subfolder"))
    )


def test_webstation_broker_host_defaults_to_the_stream_host():
    """Selkies and the broker share one port on the webstation container, and
    the subfolder is added later, so the stream host is the broker host."""
    assert (
        _broker_host_of({"host": "http://box:3010", "protocol": "webstation"})
        == "http://box:3010"
    )


def test_legacy_broker_host_still_defaults_to_port_8000():
    assert _broker_host_of({"host": "http://box:3001"}) == "http://box:8000"


def test_an_explicit_broker_host_wins_on_either_protocol():
    for protocol in ("webstation", "broker"):
        assert (
            _broker_host_of(
                {
                    "host": "https://box:3010",
                    "broker_host": "http://box:9000",
                    "protocol": protocol,
                }
            )
            == "http://box:9000"
        )


def test_a_proxied_webstation_host_derives_nothing():
    """A bare path carries no address RomM can dial, so `broker_host` stays
    required there."""
    assert _broker_host_of({"host": "/streaming", "protocol": "webstation"}) is None


# ── /sessions/{platform}/swap-disc ──────────────────────────────────────────


def _tray_container(rom: Rom, **overrides):
    """Only the webstation broker has a tray route, so every swap that is meant
    to reach the broker starts from one of these."""
    return {**_container_for(rom), "protocol": "webstation", **overrides}


def test_swap_disc_calls_the_broker_and_records_the_disc(client, access_token):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    container = _tray_container(rom)
    with _streaming(container):
        _claim_webstation_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc", return_value=True) as swap:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": disc.id},
                headers=_auth(access_token),
            )
        raw = _session_raw(container)
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "file_id": disc.id,
        "platform": rom.platform_slug,
    }
    assert swap.call_args.args[1].endswith(disc.full_path)
    assert json.loads(raw)["disc_file_id"] == disc.id


def test_swap_disc_reports_a_broker_failure(client, access_token):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    container = _tray_container(rom)
    with _streaming(container):
        _claim_webstation_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc", return_value=False):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": disc.id},
                headers=_auth(access_token),
            )
        raw = _session_raw(container)
    assert r.status_code == 502
    assert "disc_file_id" not in json.loads(raw)


def test_swap_disc_refuses_a_file_from_another_rom(client, access_token, rom):
    streamed = _rom_on("dc")
    stranger = _add_rom_file(rom, "Other.chd")
    with _streaming(_tray_container(streamed)):
        _claim_webstation_ok(client, access_token, streamed.id)
        r = client.post(
            f"/api/streaming/sessions/{streamed.platform_slug}/swap-disc",
            json={"file_id": stranger.id},
            headers=_auth(access_token),
        )
    assert r.status_code == 404


def test_swap_disc_refuses_the_m3u_playlist(client, access_token):
    """The .m3u is the playlist, not a disc; mounting it would hand the broker
    a path the emulator's tray cannot take."""
    rom = _rom_on("dc")
    playlist = _add_rom_file(rom, "Game.m3u")
    _add_rom_file(rom, "Game (Disc 2).chd")
    with _streaming(_tray_container(rom)):
        _claim_webstation_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc") as swap:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": playlist.id},
                headers=_auth(access_token),
            )
    assert r.status_code == 400
    swap.assert_not_called()


def test_swap_disc_refuses_a_raw_track_when_cues_are_present(client, access_token):
    """With .cue sheets present the raw .bin tracks they reference are not
    swap targets, matching the download endpoint's playlist filtering."""
    rom = _rom_on("dc")
    _add_rom_file(rom, "Game (Disc 2).cue")
    track = _add_rom_file(rom, "Game (Disc 2) (Track 01).bin")
    with _streaming(_tray_container(rom)):
        _claim_webstation_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc") as swap:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": track.id},
                headers=_auth(access_token),
            )
    assert r.status_code == 400
    swap.assert_not_called()


def test_swap_disc_by_other_user_is_forbidden(
    client, access_token, viewer_access_token
):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
            json={"file_id": disc.id},
            headers=_auth(viewer_access_token),
        )
    assert r.status_code == 403


def test_swap_disc_needs_a_session(client, access_token):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    with _streaming(_container_for(rom)):
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
            json={"file_id": disc.id},
            headers=_auth(access_token),
        )
    assert r.status_code == 404


def test_swap_disc_rejects_a_platform_with_no_tray(client, access_token):
    rom = _rom_on("ps2")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    with _streaming(_tray_container(rom)):
        _claim_webstation_ok(client, access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
            json={"file_id": disc.id},
            headers=_auth(access_token),
        )
    assert r.status_code == 400


def test_swap_disc_rejects_a_container_with_no_tray_route(client, access_token):
    """The platform swaps discs but this broker has no tray route, and /config
    told the frontend as much, so the refusal comes from RomM and not as a 502
    from a broker asked for a route it does not serve."""
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc") as swap:
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": disc.id},
                headers=_auth(access_token),
            )
    assert r.status_code == 400
    swap.assert_not_called()


def test_a_state_captured_after_a_swap_records_the_disc(client, access_token):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    # "dc" is in no capability table, so without an explicit emulator the
    # container resolves to the slug and every slot fails validation.
    container = _tray_container(rom, emulator="retroarch")
    with _streaming(container):
        _claim_webstation_ok(client, access_token, rom.id)
        with patch("handler.streaming.commands.swap_disc", return_value=True):
            client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/swap-disc",
                json={"file_id": disc.id},
                headers=_auth(access_token),
            )
        with (
            patch("handler.streaming.commands.save_state", return_value=True),
            _spawns_nothing(),
            patch(
                "handler.streaming.states.pull_state_to_library", new=MagicMock()
            ) as pull,
        ):
            client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-state",
                json={"slot": 10},
                headers=_auth(access_token),
            )
    assert pull.call_args.kwargs["disc_file_id"] == disc.id


def _retroarch_resume(client, token, rom, state_id):
    """Claim with a resume state on a retroarch container, launch mocked.
    Returns (response, restore mock)."""
    container = {**_container_for(rom), "emulator": "retroarch"}
    with _streaming(container):
        with (
            patch("handler.streaming.commands.launch"),
            patch("handler.streaming.states.push_resume_state", return_value=True),
            _spawns_nothing(),
            patch("handler.streaming.states.hydrate_states_to_broker", new=MagicMock()),
            patch(
                "handler.streaming.states.restore_session_disc", new=MagicMock()
            ) as restore,
        ):
            r = _claim(client, token, rom.id, state_id=state_id)
    return r, restore


def test_resuming_a_state_puts_its_disc_back(client, access_token, admin_user: User):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    state = _add_state(rom, admin_user, "Game.state", "retroarch")
    db_state_handler.update_state(state.id, {"disc_file_id": disc.id})

    r, restore = _retroarch_resume(client, access_token, rom, state.id)

    assert r.status_code == 202
    assert restore.call_args.kwargs["file_id"] == disc.id


def test_resuming_a_state_with_no_disc_swaps_nothing(
    client, access_token, admin_user: User
):
    rom = _rom_on("dc")
    state = _add_state(rom, admin_user, "Game.state", "retroarch")

    r, restore = _retroarch_resume(client, access_token, rom, state.id)

    assert r.status_code == 202
    restore.assert_not_called()


# ── _restore_session_disc (direct) ──────────────────────────────────────────


def _session_for(container: dict[str, Any], rom: Rom, user: User) -> str:
    """Seed a redis session for `container` and return its (unprefixed)
    session key, the form `_restore_session_disc` and friends take."""
    session_key = _key_of(container)
    asyncio.run(
        async_cache.set(
            session_store.session_redis_key(session_key),
            json.dumps(
                {
                    "rom_id": rom.id,
                    "rom_name": rom.name,
                    "platform": rom.platform_slug,
                    "claimed_at": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "user_id": user.id,
                }
            ),
        )
    )
    return session_key


def test_restore_session_disc_swaps_and_records_the_disc(admin_user: User):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    container = _container_for(rom)
    session_key = _session_for(container, rom, admin_user)
    with patch("handler.streaming.commands.swap_disc", return_value=True) as swap:
        ok = asyncio.run(
            states.restore_session_disc(
                rom.id, _resolved(container), session_key, file_id=disc.id
            )
        )
    assert ok is True
    assert swap.call_args.args[1].endswith(disc.full_path)
    raw = _session_raw(container)
    assert json.loads(raw)["disc_file_id"] == disc.id


def test_restore_session_disc_refuses_a_file_from_another_rom(
    admin_user: User, rom: Rom
):
    streamed = _rom_on("dc")
    stranger = _add_rom_file(rom, "Other.chd")
    container = _container_for(streamed)
    session_key = _session_for(container, streamed, admin_user)
    with patch("handler.streaming.commands.swap_disc") as swap:
        ok = asyncio.run(
            states.restore_session_disc(
                streamed.id, container, session_key, file_id=stranger.id
            )
        )
    assert ok is False
    swap.assert_not_called()
    raw = _session_raw(container)
    assert "disc_file_id" not in json.loads(raw)


def test_restore_session_disc_bails_out_when_the_file_is_gone(admin_user: User, caplog):
    rom = _rom_on("dc")
    container = _container_for(rom)
    session_key = _session_for(container, rom, admin_user)
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with (
            patch("handler.streaming.commands.swap_disc") as swap,
            caplog.at_level(logging.WARNING, logger="romm"),
        ):
            ok = asyncio.run(
                states.restore_session_disc(
                    rom.id, container, session_key, file_id=999999
                )
            )
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert ok is False
    swap.assert_not_called()
    assert "not in the library" in caplog.text


def test_restore_session_disc_does_not_record_on_broker_failure(admin_user: User):
    rom = _rom_on("dc")
    disc = _add_rom_file(rom, "Game (Disc 2).chd")
    container = _container_for(rom)
    session_key = _session_for(container, rom, admin_user)
    with patch("handler.streaming.commands.swap_disc", return_value=False):
        ok = asyncio.run(
            states.restore_session_disc(
                rom.id, _resolved(container), session_key, file_id=disc.id
            )
        )
    assert ok is False
    raw = _session_raw(container)
    assert "disc_file_id" not in json.loads(raw)


async def test_store_save_asset_fits_a_long_multibyte_rom_name(
    admin_user: User, rom: Rom
):
    """A ROM name can be far over the 255-byte filename limit once encoded;
    the pulled archive must still be stored rather than dropped."""
    rom.fs_name_no_ext = "ゲーム" * 50
    scanned = Save(file_name="pulled.saves.zip")
    with (
        patch(
            "handler.streaming.saves.fs_asset_handler.write_file", new=AsyncMock()
        ) as write,
        patch.object(saves, "scan_save", new=AsyncMock(return_value=scanned)),
        patch("handler.streaming.saves.db_save_handler.add_save") as add_save,
    ):
        assert await saves.store_save_asset(admin_user, rom, "pcsx2", b"zip")

    filename = write.call_args.kwargs["filename"]
    assert len(filename.encode()) <= 255
    assert filename.startswith("ゲーム")
    assert filename.endswith("].saves.zip")
    add_save.assert_called_once()


# ── streaming permission ──────────────────────────────────────────────────────


def _override_streaming(
    user: User, *actions: PermAction, granted: bool = False, own_only: bool = False
) -> None:
    with sync_session.begin() as s:
        for action in actions:
            s.add(
                UserPermissionOverride(
                    user_id=user.id,
                    entity=PermEntity.STREAMING,
                    action=action,
                    granted=granted,
                    own_only=own_only,
                )
            )


def test_get_config_is_disabled_without_streaming_read(
    client, viewer_access_token, viewer_user: User, rom: Rom
):
    """A user kept off streaming gets the same answer as a server without it."""
    _override_streaming(viewer_user, PermAction.READ)
    with _streaming(_container_for(rom)):
        response = client.get(
            "/api/streaming/config", headers=_auth(viewer_access_token)
        )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["containers"] == []


@pytest.fixture
def guests_group() -> Iterator[int]:
    """A group with no streaming grant; conftest keeps groups between tests."""
    with sync_session.begin() as s:
        group = PermissionGroup(
            name="Guests",
            grants=[
                PermissionGroupGrant(entity=PermEntity.ROMS, action=PermAction.READ)
            ],
        )
        s.add(group)
        s.flush()
        group_id = group.id
    yield group_id
    with sync_session.begin() as s:
        s.query(PermissionGroup).filter_by(id=group_id).delete()


def test_get_config_is_disabled_for_a_group_without_streaming(
    client, rom: Rom, guests_group: int
):
    """A group an admin creates starts with no streaming grant."""
    guest = db_user_handler.add_user(
        User(username="guest", role=Role.USER, permission_group_id=guests_group)
    )
    with _streaming(_container_for(rom)):
        response = client.get(
            "/api/streaming/config", headers=_auth(_access_token(guest))
        )
    assert response.json()["enabled"] is False


def test_get_config_keeps_streaming_for_an_admin_with_no_grants(
    client, access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        response = client.get("/api/streaming/config", headers=_auth(access_token))
    assert response.json()["enabled"] is True


@pytest.mark.parametrize("action", [PermAction.READ, PermAction.WRITE])
def test_claim_without_streaming_grant_is_forbidden(
    client, viewer_access_token, viewer_user: User, rom: Rom, action: PermAction
):
    """Starting a session takes a container, so it needs both grants."""
    _override_streaming(viewer_user, action)
    with _streaming(_container_for(rom)):
        with patch("handler.streaming.commands.launch") as call_broker:
            r = _claim(client, viewer_access_token, rom.id)
    assert r.status_code == 403
    call_broker.assert_not_called()


def test_an_own_only_streaming_grant_counts(
    client, viewer_access_token, viewer_user: User, rom: Rom
):
    """A session the player starts is their own, so "own items only" counts."""
    _override_streaming(
        viewer_user, PermAction.READ, PermAction.WRITE, granted=True, own_only=True
    )
    with _streaming(_container_for(rom)):
        config = client.get("/api/streaming/config", headers=_auth(viewer_access_token))
        r = _claim_ok(client, viewer_access_token, rom.id)
    assert config.json()["enabled"] is True
    assert r.status_code == 202


def test_claim_with_streaming_grant_still_launches(
    client, viewer_access_token, rom: Rom
):
    with _streaming(_container_for(rom)):
        r = _claim_ok(client, viewer_access_token, rom.id)
    assert r.status_code == 202


def test_joining_without_streaming_read_is_forbidden(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    _override_streaming(viewer_user, PermAction.READ)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        with patch("handler.streaming.webstation.join") as join_broker:
            response = _join(client, viewer_access_token, rom.platform_slug)
    assert response.status_code == 403
    join_broker.assert_not_called()


def test_joining_needs_only_streaming_read(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """A guest seat runs on the host's container, so it costs no launch."""
    _override_streaming(viewer_user, PermAction.WRITE)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        body = _joinable(client, viewer_access_token).json()
        with _joined_room():
            joined = _join(client, viewer_access_token, rom.platform_slug)
    assert len(body["sessions"]) == 1
    assert joined.status_code == 200


def test_an_own_only_streaming_read_cannot_join_someone_elses_session(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    """Another player's session is not the caller's own."""
    _override_streaming(viewer_user, PermAction.READ, granted=True, own_only=True)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        listed = _joinable(client, viewer_access_token)
        with patch("handler.streaming.webstation.join") as join_broker:
            joined = _join(client, viewer_access_token, rom.platform_slug)
    assert listed.status_code == 200
    assert listed.json()["sessions"] == []
    assert joined.status_code == 403
    join_broker.assert_not_called()


def test_joinable_is_empty_without_streaming_read(
    client, access_token, viewer_access_token, viewer_user: User, rom: Rom
):
    _override_streaming(viewer_user, PermAction.READ)
    with _streaming(_ws_for(rom)):
        _claim_multiplayer(client, access_token, rom.id)
        response = _joinable(client, viewer_access_token)
    assert response.status_code == 200
    assert response.json()["sessions"] == []


def test_a_revoked_player_can_still_leave_their_session(
    client, viewer_access_token, viewer_user: User, rom: Rom
):
    """Revoking streaming mid-game must not strand the player's save."""
    with _streaming(_container_for(rom)):
        assert _claim_ok(client, viewer_access_token, rom.id).status_code == 202
        _override_streaming(viewer_user, PermAction.READ, PermAction.WRITE)
        with _stub_stop():
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(viewer_access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"
