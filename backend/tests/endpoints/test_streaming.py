import asyncio
import io
import json
import logging
import re
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app

from config import LIBRARY_BASE_PATH, OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from endpoints import streaming
from handler.auth import oauth_handler
from handler.database import (
    db_memory_card_handler,
    db_platform_handler,
    db_play_session_handler,
    db_rom_handler,
    db_save_handler,
    db_state_handler,
)
from handler.database.base_handler import sync_session
from handler.redis_handler import async_cache
from models.assets import MemoryCard, MemoryCardVersion, Save, Screenshot, State
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User

# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_streaming_sessions():
    """Streaming sessions live in Redis (fakeredis under pytest), start clean."""
    asyncio.run(async_cache.flushall())
    yield


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


def _mock_cm(enabled=True, containers=None):
    """Return a mock config_manager that yields the given streaming config."""
    cfg = MagicMock()
    cfg.STREAMING_ENABLED = enabled
    cfg.STREAMING_CONTAINERS = containers or []
    return cfg


@contextmanager
def _streaming(*containers, enabled=True):
    """Patch the streaming config to serve exactly the given containers."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(enabled=enabled, containers=list(containers)),
    ):
        yield


def _container_for(rom: Rom, broker_host="http://192.168.1.10:8000"):
    return {
        "platform": rom.platform_slug,
        "host": "http://192.168.1.10:3000",
        "broker_host": broker_host,
    }


def _rom_on(slug: str) -> Rom:
    """Create a platform with the given slug and a ROM on it."""
    platform = db_platform_handler.add_platform(
        Platform(name=slug, slug=slug, fs_slug=slug)
    )
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=f"{slug}-rom",
            slug=f"{slug}-rom",
            fs_name=f"{slug}.zip",
            fs_name_no_tags=slug,
            fs_name_no_ext=slug,
            fs_extension="zip",
            fs_path=f"{slug}/roms",
        )
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _claim(client, token, rom_id, state_id=None):
    body = {"rom_id": rom_id}
    if state_id is not None:
        body["state_id"] = state_id
    return client.post("/api/streaming/sessions", json=body, headers=_auth(token))


def _claim_ok(client, token, rom_id):
    """Claim with the broker launch stubbed, the common happy-path setup."""
    with patch("endpoints.streaming._call_broker"):
        return _claim(client, token, rom_id)


# ── /config ───────────────────────────────────────────────────────────────────


def test_get_config_requires_auth(client):
    assert client.get("/api/streaming/config").status_code == 403


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
    }


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


# ── Claiming ──────────────────────────────────────────────────────────────────


def test_claim_derives_rom_path_server_side(client, access_token, rom: Rom):
    """The broker must receive a path built from the DB row, not client input."""
    with _streaming(_container_for(rom)):
        with patch("endpoints.streaming._call_broker") as call_broker:
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["rom_name"] == rom.name
    _, rom_path, _, _ = call_broker.call_args[0]
    assert rom_path == f"{LIBRARY_BASE_PATH}/{rom.full_path}"


def test_claim_honors_container_library_path(client, access_token, rom: Rom):
    """`library_path` on the container entry replaces LIBRARY_BASE_PATH so the
    broker gets a path valid inside a container with a different mount."""
    container = {**_container_for(rom), "library_path": "/mnt/games/"}
    with _streaming(container):
        with patch("endpoints.streaming._call_broker") as call_broker:
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    _, rom_path, _, _ = call_broker.call_args[0]
    assert rom_path == f"/mnt/games/{rom.full_path}"


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
        with patch("endpoints.streaming._call_broker") as call_broker:
            r = _claim(client, viewer_access_token, rom.id)
    assert r.status_code == 404
    call_broker.assert_not_called()


def test_claim_rom_on_hidden_platform_is_404_masked(
    client, viewer_access_token, viewer_user: User, rom: Rom, platform: Platform
):
    """Hiding the parent platform cascades: its ROMs cannot be streamed either."""
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    with _streaming(_container_for(rom)):
        with patch("endpoints.streaming._call_broker") as call_broker:
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


@pytest.mark.asyncio
async def test_claim_sets_session_ttl(access_token, rom: Rom):
    """A claimed session must carry a TTL so an abandoned one eventually frees
    the container instead of wedging it forever."""
    with _streaming(_container_for(rom)):
        with patch("endpoints.streaming._call_broker"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r = await ac.post(
                    "/api/streaming/sessions",
                    json={"rom_id": rom.id},
                    headers=_auth(access_token),
                )
    assert r.status_code == 200
    key = streaming._session_redis_key(streaming._container_key(_container_for(rom)))
    ttl = await async_cache.ttl(key)
    assert ttl > 0
    assert ttl <= streaming.SESSION_TTL_SECONDS


def test_second_claim_on_same_container_rejected(client, access_token, rom: Rom):
    """The container is single-tenant: a second claim must 409 with the holder."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom.id)
    assert r1.status_code == 200
    assert r2.status_code == 409
    assert r2.json()["detail"]["rom_name"] == rom.name


def test_claim_session_same_container_two_platforms_rejected(
    client, access_token, admin_user: User, rom: Rom
):
    """Dolphin serves ngc and wii from one broker - second claim must be 409."""
    platform2 = db_platform_handler.add_platform(
        Platform(name="p2", slug="p2_slug", fs_slug="p2_slug")
    )
    rom2 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform2.id,
            name="rom2",
            slug="rom2",
            fs_name="rom2.zip",
            fs_name_no_tags="rom2",
            fs_name_no_ext="rom2",
            fs_extension="zip",
            fs_path=f"{platform2.slug}/roms",
        )
    )
    shared_broker = "http://192.168.1.10:8000"
    with _streaming(
        _container_for(rom, broker_host=shared_broker),
        _container_for(rom2, broker_host=shared_broker),
    ):
        r1 = _claim_ok(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom2.id)
    assert r1.status_code == 200
    assert r2.status_code == 409


def test_failed_broker_launch_frees_the_claim(client, access_token, rom: Rom):
    """If the broker rejects the launch, the container must not stay claimed."""
    with _streaming(_container_for(rom)):
        with patch(
            "endpoints.streaming._call_broker",
            side_effect=HTTPException(status_code=503, detail="unreachable"),
        ):
            r1 = _claim(client, access_token, rom.id)
        r2 = _claim_ok(client, access_token, rom.id)
    assert r1.status_code == 503
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_claim_only_one_succeeds(access_token, rom: Rom):
    """Two concurrent claims on one container: exactly one 200 and one 409."""
    with _streaming(_container_for(rom)):
        with patch("endpoints.streaming._call_broker"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
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
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]


# ── Staleness / heartbeat ─────────────────────────────────────────────────────


def _age_session(rom: Rom, seconds: int) -> None:
    """Rewrite the stored session's last_seen to `seconds` ago."""
    key = streaming._session_redis_key(streaming._container_key(_container_for(rom)))
    raw = asyncio.run(async_cache.get(key))
    session = json.loads(raw)
    session["last_seen"] = (
        datetime.now(timezone.utc) - timedelta(seconds=seconds)
    ).isoformat()
    asyncio.run(async_cache.set(key, json.dumps(session)))


def test_session_is_stale_handles_bad_stamps():
    """Missing or corrupt stamps must count as stale, not wedge the container."""
    assert streaming._session_is_stale({}) is True
    assert streaming._session_is_stale({"last_seen": "not-a-date"}) is True
    fresh = datetime.now(timezone.utc).isoformat()
    assert streaming._session_is_stale({"last_seen": fresh}) is False
    old = (
        datetime.now(timezone.utc)
        - timedelta(seconds=streaming._SESSION_STALE_SECONDS + 1)
    ).isoformat()
    assert streaming._session_is_stale({"last_seen": old}) is True


def test_stale_session_taken_over_on_claim(
    client, access_token, viewer_access_token, rom: Rom
):
    """A claim against a session whose heartbeat stopped must tear the old
    session down (broker stop included) and win the container."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        _age_session(rom, streaming._SESSION_STALE_SECONDS + 60)
        with patch("endpoints.streaming._stop_broker") as stop_broker:
            r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert r1.status_code == 200
    assert r2.status_code == 200
    stop_broker.assert_called_once()


def test_fresh_session_not_taken_over(
    client, access_token, viewer_access_token, rom: Rom
):
    """A session with a live heartbeat keeps its claim: second claim is 409
    and the running emulator is never stopped."""
    with _streaming(_container_for(rom)):
        r1 = _claim_ok(client, access_token, rom.id)
        with patch("endpoints.streaming._stop_broker") as stop_broker:
            r2 = _claim_ok(client, viewer_access_token, rom.id)
    assert r1.status_code == 200
    assert r2.status_code == 409
    stop_broker.assert_not_called()


def test_heartbeat_refreshes_last_seen(client, access_token, rom: Rom):
    """A heartbeat on an aged session must reset its staleness clock so a
    rival claim no longer takes it over."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, streaming._SESSION_STALE_SECONDS + 60)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/heartbeat",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    key = streaming._session_redis_key(streaming._container_key(_container_for(rom)))
    session = json.loads(asyncio.run(async_cache.get(key)))
    assert not streaming._session_is_stale(session)


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
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    assert r.status_code == 200
    assert r.json() == {"status": "active", "platform": rom.platform_slug}


def test_status_does_not_refresh_the_session(client, access_token, rom: Rom):
    """Status is read-only: polling it must not extend a claim, otherwise a
    background tab could keep a container hostage without playing."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        _age_session(rom, streaming._SESSION_STALE_SECONDS + 60)
        client.get(
            f"/api/streaming/sessions/{rom.platform_slug}/status",
            headers=_auth(access_token),
        )
    key = streaming._session_redis_key(streaming._container_key(_container_for(rom)))
    session = json.loads(asyncio.run(async_cache.get(key)))
    assert streaming._session_is_stale(session)


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


def test_self_release_leaves_no_termination_notice(client, access_token, rom: Rom):
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


# ── Release / ownership ───────────────────────────────────────────────────────


def test_release_uses_container_key_not_platform(client, access_token, rom: Rom):
    """release_session must find the session by broker_host, not platform string."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch("endpoints.streaming._stop_broker"):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"


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
    assert r_claim.status_code == 200
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


def test_save_and_exit_releases_session(client, access_token, rom: Rom):
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._save_and_exit_broker", return_value=(True, 10)),
            # Plain MagicMock: the async original would auto-mock to AsyncMock,
            # whose call handed to the mocked spawn is a never-awaited coroutine.
            patch("endpoints.streaming._pull_state_to_library", new=MagicMock()),
            patch("endpoints.streaming._pull_saves_to_library", new=MagicMock()),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 10, "wait": True},
                headers=_auth(access_token),
            )
        # Container must be claimable again after save-and-exit.
        r2 = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert r2.status_code == 200


def test_save_and_exit_failure_still_releases_session(client, access_token, rom: Rom):
    """A failed save is reported as saved=False, but the session is still
    released - the container must not stay claimed by a dead session."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch(
            "endpoints.streaming._save_and_exit_broker", return_value=(False, 10)
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 10, "wait": True},
                headers=_auth(access_token),
            )
        r2 = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is False
    assert r2.status_code == 200


def test_force_release_all_stops_brokers(client, access_token, rom: Rom):
    """Force-release must tell each broker to stop, not just clear Redis."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with patch("endpoints.streaming._stop_broker") as stop_broker:
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
        with patch("endpoints.streaming._save_state_broker", return_value=True):
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
        with patch("endpoints.streaming._load_state_broker", return_value=True):
            r = client.post(
                "/api/streaming/sessions/wii/load-state",
                json={"slot": 8},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    assert r.json()["loaded"] is True


def test_load_state_rejects_slot_between_max_and_autosave(client, access_token):
    """Dolphin: slot 9 is neither a manual slot (1-7) nor the autosave (8)."""
    rom = _rom_on("wiiu")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        r = client.post(
            "/api/streaming/sessions/wiiu/load-state",
            json={"slot": 9},
            headers=_auth(access_token),
        )
    assert r.status_code == 422


def _state_for(rom: Rom, user: User, file_name: str, emulator: str) -> State:
    name_no_ext, _, extension = file_name.rpartition(".")
    return State(
        rom_id=rom.id,
        user_id=user.id,
        file_name=file_name,
        file_name_no_tags=name_no_ext,
        file_name_no_ext=name_no_ext,
        file_extension=extension,
        emulator=emulator,
        file_path=f"{rom.platform_slug}/states/{emulator}",
        file_size_bytes=1.0,
    )


def test_claim_spawns_state_hydration(client, access_token, rom: Rom):
    """Claiming a session must schedule a background hydration of the
    container's save-state slots from the user's stored states."""
    with _streaming(_container_for(rom)):
        with (
            patch("endpoints.streaming._call_broker"),
            patch("endpoints.streaming._spawn_sync_task") as spawn,
            patch(
                "endpoints.streaming._hydrate_states_to_broker", new=MagicMock()
            ) as hydrate,
        ):
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    spawn.assert_called_once()
    assert hydrate.call_args[0][1] == rom.id


def test_save_state_spawns_library_pull(client, access_token):
    """Every manual save-state must schedule a background pull to the library."""
    rom = _rom_on("ps2")
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._save_state_broker", return_value=True),
            patch("endpoints.streaming._spawn_sync_task") as spawn,
            patch(
                "endpoints.streaming._pull_state_to_library", new=MagicMock()
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
            patch("endpoints.streaming._save_and_exit_broker", return_value=(True, 10)),
            patch("endpoints.streaming._spawn_sync_task") as spawn,
            patch(
                "endpoints.streaming._pull_state_to_library", new=MagicMock()
            ) as pull,
            patch("endpoints.streaming._pull_saves_to_library", new=MagicMock()),
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
                "endpoints.streaming._save_and_exit_broker", return_value=(False, 10)
            ),
            patch("endpoints.streaming._spawn_sync_task") as spawn,
            patch(
                "endpoints.streaming._pull_state_to_library", new=MagicMock()
            ) as state_pull,
            patch(
                "endpoints.streaming._pull_saves_to_library", new=MagicMock()
            ) as save_pull,
        ):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 10, "wait": True},
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    state_pull.assert_not_called()
    save_pull.assert_called_once()
    spawn.assert_called_once()


def test_save_and_exit_wait_false_drains_instead_of_freeing(
    client, access_token, rom: Rom
):
    """wait=false means the broker is still killing in the background; the
    session key must briefly block a re-claim (drain) rather than be deleted
    immediately, so a new launch can't land on a not-yet-dead emulator."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._save_and_exit_broker", return_value=(True, 10)),
            patch("endpoints.streaming._pull_state_to_library", new=MagicMock()),
            patch("endpoints.streaming._pull_saves_to_library", new=MagicMock()),
            patch("endpoints.streaming._spawn_sync_task"),
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
    # Drain TTL is bounded to the short window, not the full session TTL.
    key = streaming._session_redis_key(streaming._container_key(_container_for(rom)))
    ttl = asyncio.run(async_cache.ttl(key))
    assert 0 < ttl <= streaming.SESSION_DRAIN_SECONDS


def test_pull_state_to_library_stores_state(rom: Rom, admin_user: User):
    """A pulled state file lands in the user's state library under the
    container's emulator namespace, keyed by the broker-supplied filename."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    with (
        patch(
            "endpoints.streaming._fetch_state_file",
            return_value=("Game.03.p2s", b"state-bytes"),
        ),
        patch("endpoints.streaming._fetch_state_screenshot", return_value=None),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("endpoints.streaming.scan_state", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            streaming._pull_state_to_library(admin_user.id, rom.id, container, 3)
        )
    assert ok is True
    wf.assert_awaited_once()
    # The library keeps every capture, so the stored name carries a stamp ahead of
    # the slot token; the container-side name is recovered by dropping it.
    stored_name = wf.await_args_list[0].kwargs["filename"]
    assert re.fullmatch(r"Game\.\d{8}-\d{12}\.03\.p2s", stored_name)
    assert streaming._container_state_filename(stored_name) == "Game.03.p2s"
    db_state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert db_state is not None
    assert db_state.emulator == "pcsx2"


def test_pull_state_falls_back_to_broker_screenshot(rom: Rom, admin_user: User):
    """Dolphin states embed no frame, so the pull takes the broker's capture."""
    container = {**_container_for(rom), "label": "Dolphin"}
    scanned = _state_for(rom, admin_user, "Game.s03", "dolphin")
    scanned_shot = Screenshot(
        file_name="Game.s03.png",
        file_name_no_tags="Game.s03",
        file_name_no_ext="Game.s03",
        file_extension="png",
        file_path=f"{rom.platform_slug}/screenshots",
        file_size_bytes=7,
    )
    with (
        patch(
            "endpoints.streaming._fetch_state_file",
            return_value=("Game.s03", b"state-bytes"),
        ),
        patch(
            "endpoints.streaming._fetch_state_screenshot", return_value=b"PNGDATA"
        ) as fetch_shot,
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()),
        patch("endpoints.streaming.scan_state", new=AsyncMock(return_value=scanned)),
        patch(
            "endpoints.streaming.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ) as scan_shot,
    ):
        ok = asyncio.run(
            streaming._pull_state_to_library(admin_user.id, rom.id, container, 3)
        )
    assert ok is True
    fetch_shot.assert_called_once()
    scan_shot.assert_awaited_once()
    db_state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.s03"
    )
    assert db_state is not None
    assert db_state.screenshot is not None


def test_pull_state_rejects_unsanitizable_filename(rom: Rom, admin_user: User):
    """A broker filename that sanitizes to nothing must be dropped, not stored."""
    with (
        patch("endpoints.streaming._fetch_state_file", return_value=("***", b"bytes")),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            streaming._pull_state_to_library(
                admin_user.id, rom.id, _container_for(rom), 1
            )
        )
    assert ok is False
    wf.assert_not_awaited()


def test_hydrate_pushes_only_matching_emulator_states(rom: Rom, admin_user: User):
    """Hydration must push only states saved under this container's emulator
    namespace - EmulatorJS states for the same ROM stay out of the container."""
    db_state_handler.add_state(_state_for(rom, admin_user, "Game.01.p2s", "pcsx2"))
    db_state_handler.add_state(_state_for(rom, admin_user, "Game.state", "retroarch"))
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("endpoints.streaming._push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            streaming._hydrate_states_to_broker(admin_user.id, rom.id, container)
        )
    assert pushed == 1
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.01.p2s"


def test_hydrate_skips_states_missing_on_disk(rom: Rom, admin_user: User):
    """A DB row whose file vanished from disk is skipped, not fatal."""
    db_state_handler.add_state(_state_for(rom, admin_user, "Game.01.p2s", "pcsx2"))
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("endpoints.streaming._push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            streaming._hydrate_states_to_broker(admin_user.id, rom.id, container)
        )
    assert pushed == 0
    push.assert_not_called()


def _add_state_at(rom: Rom, user: User, file_name: str, day: int) -> State:
    """Add a state with an explicit updated_at, so history order is deterministic."""
    state = _state_for(rom, user, file_name, "pcsx2")
    stored = db_state_handler.add_state(state)
    db_state_handler.update_state(
        stored.id, {"updated_at": datetime(2026, 1, day, tzinfo=timezone.utc)}
    )
    return stored


def test_hydrate_skipped_when_resume_state_already_pushed(rom: Rom, admin_user: User):
    """Every history entry collapses to the same container-side name, so pushing
    anything here would overwrite the state the player picked to resume from."""
    db_state_handler.add_state(_state_for(rom, admin_user, "Game.01.p2s", "pcsx2"))
    container = {**_container_for(rom), "label": "PCSX2"}
    with patch("endpoints.streaming._push_state_file", return_value=True) as push:
        pushed = asyncio.run(
            streaming._hydrate_states_to_broker(
                admin_user.id, rom.id, container, resume_pushed=True
            )
        )
    assert pushed == 0
    push.assert_not_called()


def test_hydrate_pushes_newest_state_under_container_name(rom: Rom, admin_user: User):
    """Only the newest capture is hydrated, and it lands under the unstamped name
    the emulator expects on disk."""
    _add_state_at(rom, admin_user, "Game.20260101-000000000000.01.p2s", 1)
    _add_state_at(rom, admin_user, "Game.20260202-000000000000.01.p2s", 2)
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"state-bytes"),
        ),
        patch("endpoints.streaming._push_state_file", return_value=True) as push,
    ):
        pushed = asyncio.run(
            streaming._hydrate_states_to_broker(admin_user.id, rom.id, container)
        )
    assert pushed == 1
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.01.p2s"


def test_pull_state_skips_capture_identical_to_previous(rom: Rom, admin_user: User):
    """Saving twice without playing in between produces the same bytes, and the
    duplicate must not take a history slot."""
    content = b"state-bytes"
    existing = _state_for(rom, admin_user, "Game.20260101-000000000000.03.p2s", "pcsx2")
    existing.file_size_bytes = len(content)
    db_state_handler.add_state(existing)
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "endpoints.streaming._fetch_state_file",
            return_value=("Game.03.p2s", content),
        ),
        patch("endpoints.streaming._fetch_state_screenshot", return_value=None),
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(return_value=content),
        ),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            streaming._pull_state_to_library(admin_user.id, rom.id, container, 3)
        )
    assert ok is True
    wf.assert_not_awaited()


def test_prune_state_history_drops_oldest_past_limit(rom: Rom, admin_user: User):
    """Once the retention limit is reached the oldest captures go, newest first
    order preserved."""
    for day in range(1, 4):
        _add_state_at(rom, admin_user, f"Game.2026010{day}-000000000000.01.p2s", day)
    with (
        patch("endpoints.streaming.STREAMING_STATE_HISTORY_LIMIT", 2),
        patch(
            "endpoints.streaming.fs_asset_handler.remove_file", new=AsyncMock()
        ) as remove,
    ):
        pruned = asyncio.run(streaming._prune_state_history(admin_user, rom, "pcsx2"))
    assert pruned == 1
    remove.assert_awaited_once()
    remaining = {
        s.file_name
        for s in db_state_handler.get_states(user_id=admin_user.id, rom_id=rom.id)
    }
    assert remaining == {
        "Game.20260102-000000000000.01.p2s",
        "Game.20260103-000000000000.01.p2s",
    }


def _p2s_bytes(screenshot: bytes | None = b"PNGDATA") -> bytes:
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
    assert streaming._extract_state_screenshot("pcsx2", _p2s_bytes(b"PNG")) == b"PNG"


def test_extract_state_screenshot_non_pcsx2_returns_none():
    # Dolphin states embed no frame; its broker serves one from /state-screenshot.
    assert streaming._extract_state_screenshot("dolphin", _p2s_bytes()) is None


def test_extract_state_screenshot_missing_entry_returns_none():
    assert streaming._extract_state_screenshot("pcsx2", _p2s_bytes(None)) is None


def test_extract_state_screenshot_empty_entry_returns_none():
    assert streaming._extract_state_screenshot("pcsx2", _p2s_bytes(b"")) is None


def test_extract_state_screenshot_not_a_zip_returns_none():
    assert streaming._extract_state_screenshot("pcsx2", b"not-a-zip") is None


def test_fetch_state_screenshot_returns_png(rom: Rom):
    resp = MagicMock()
    resp.__enter__.return_value.read.return_value = b"PNGDATA"
    with patch("endpoints.streaming.urllib.request.urlopen", return_value=resp):
        assert streaming._fetch_state_screenshot(_container_for(rom), 1) == b"PNGDATA"


def test_fetch_state_screenshot_404_returns_none(rom: Rom):
    """A broker that captures no frames answers 404; that is not an error."""
    with patch(
        "endpoints.streaming.urllib.request.urlopen", side_effect=_http_error(404)
    ):
        assert streaming._fetch_state_screenshot(_container_for(rom), 1) is None


def test_fetch_state_screenshot_transport_error_returns_none(rom: Rom):
    import urllib.error

    with patch(
        "endpoints.streaming.urllib.request.urlopen",
        side_effect=urllib.error.URLError("broker down"),
    ):
        assert streaming._fetch_state_screenshot(_container_for(rom), 1) is None


def test_store_state_screenshot_binds_to_state(admin_user: User, rom: Rom):
    """A stored state screenshot lands in the screenshots dir under the state's
    stem, so State.screenshot resolves it as the resume-picker thumbnail."""
    db_state_handler.add_state(_state_for(rom, admin_user, "Game.03.p2s", "pcsx2"))
    scanned = Screenshot(
        file_name="Game.03.png",
        file_name_no_tags="Game.03",
        file_name_no_ext="Game.03",
        file_extension="png",
        file_path=f"{rom.platform_slug}/screenshots",
        file_size_bytes=7,
    )
    with (
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch(
            "endpoints.streaming.scan_screenshot",
            new=AsyncMock(return_value=scanned),
        ),
    ):
        asyncio.run(
            streaming._store_state_screenshot(
                admin_user, rom, "Game.03.p2s", b"PNGDATA"
            )
        )
    wf.assert_awaited_once()
    assert wf.await_args_list[0].kwargs["filename"] == "Game.03.png"
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert state.screenshot is not None
    assert state.screenshot.file_name == "Game.03.png"
    assert state.screenshot.is_gallery is False


def test_store_state_asset_binds_screenshot(admin_user: User, rom: Rom):
    """End to end: storing a state with a frame binds it as the thumbnail."""
    scanned_state = _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    scanned_shot = Screenshot(
        file_name="Game.03.png",
        file_name_no_tags="Game.03",
        file_name_no_ext="Game.03",
        file_extension="png",
        file_path=f"{rom.platform_slug}/screenshots",
        file_size_bytes=7,
    )
    with (
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "endpoints.streaming.scan_state",
            new=AsyncMock(return_value=scanned_state),
        ),
        patch(
            "endpoints.streaming.scan_screenshot",
            new=AsyncMock(return_value=scanned_shot),
        ) as scan_shot,
    ):
        asyncio.run(
            streaming._store_state_asset(
                admin_user, rom, "pcsx2", "Game.03.p2s", _p2s_bytes(b"PNG"), b"PNG"
            )
        )
    scan_shot.assert_awaited_once()
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.03.p2s"
    )
    assert state.screenshot is not None
    assert state.screenshot.file_name == "Game.03.png"


def test_store_state_asset_without_screenshot_still_stores_state(
    admin_user: User, rom: Rom
):
    """A state with no frame syncs with no thumbnail; the missing screenshot
    must not fail the state sync."""
    scanned_state = _state_for(rom, admin_user, "Game.04.p2s", "pcsx2")
    with (
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "endpoints.streaming.scan_state",
            new=AsyncMock(return_value=scanned_state),
        ),
        patch("endpoints.streaming.scan_screenshot", new=AsyncMock()) as scan_shot,
    ):
        asyncio.run(
            streaming._store_state_asset(
                admin_user, rom, "pcsx2", "Game.04.p2s", _p2s_bytes(None)
            )
        )
    scan_shot.assert_not_awaited()
    state = db_state_handler.get_state_by_filename(
        user_id=admin_user.id, rom_id=rom.id, file_name="Game.04.p2s"
    )
    assert state is not None
    assert state.screenshot is None


# ── In-game save sync ─────────────────────────────────────────────────────────


def _save_for(
    rom: Rom, user: User, file_name: str, emulator: str, content_hash: str | None = None
) -> Save:
    name_no_ext, _, extension = file_name.rpartition(".")
    return Save(
        rom_id=rom.id,
        user_id=user.id,
        file_name=file_name,
        file_name_no_tags=name_no_ext,
        file_name_no_ext=name_no_ext,
        file_extension=extension,
        emulator=emulator,
        content_hash=content_hash,
        file_path=f"{rom.platform_slug}/saves/{emulator}",
        file_size_bytes=1.0,
    )


def test_pull_saves_stores_new_archive(rom: Rom, admin_user: User):
    """A pulled save archive lands as a new Save asset under the container's
    emulator namespace."""
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _save_for(rom, admin_user, "Game [pcsx2].saves.zip", "pcsx2", "hash-a")
    with (
        patch("endpoints.streaming._fetch_save_archive", return_value=b"zip-bytes"),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch("endpoints.streaming.scan_save", new=AsyncMock(return_value=scanned)),
    ):
        ok = asyncio.run(
            streaming._pull_saves_to_library(admin_user.id, rom.id, container)
        )
    assert ok is True
    wf.assert_awaited_once()
    saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
    assert any(s.emulator == "pcsx2" and s.content_hash == "hash-a" for s in saves)


def test_pull_saves_dedups_identical_archive(rom: Rom, admin_user: User):
    """Re-pulling an unchanged archive (same content hash) must not add a second
    row, and must delete the just-written duplicate file."""
    db_save_handler.add_save(
        _save_for(rom, admin_user, "Game [pcsx2 old].saves.zip", "pcsx2", "dup-hash")
    )
    container = {**_container_for(rom), "label": "PCSX2"}
    scanned = _save_for(
        rom, admin_user, "Game [pcsx2 new].saves.zip", "pcsx2", "dup-hash"
    )
    with (
        patch("endpoints.streaming._fetch_save_archive", return_value=b"zip-bytes"),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()),
        patch("endpoints.streaming.scan_save", new=AsyncMock(return_value=scanned)),
        patch(
            "endpoints.streaming.fs_asset_handler.remove_file", new=AsyncMock()
        ) as rm,
    ):
        ok = asyncio.run(
            streaming._pull_saves_to_library(admin_user.id, rom.id, container)
        )
    assert ok is True
    rm.assert_awaited_once()
    saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
    hashes = [s.content_hash for s in saves if s.emulator == "pcsx2"]
    assert hashes == ["dup-hash"]


def test_pull_saves_no_changes_returns_false(rom: Rom, admin_user: User):
    """A 404 from the broker (nothing changed) yields no stored save."""
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch("endpoints.streaming._fetch_save_archive", return_value=None),
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
    ):
        ok = asyncio.run(
            streaming._pull_saves_to_library(admin_user.id, rom.id, container)
        )
    assert ok is False
    wf.assert_not_awaited()


def test_hydrate_saves_pushes_newest_matching_zip(rom: Rom, admin_user: User):
    """Hydration pushes the newest .zip save for this container's emulator, and
    ignores non-zip saves and other emulators' saves."""
    db_save_handler.add_save(
        _save_for(rom, admin_user, "Game [pcsx2 a].saves.zip", "pcsx2", "h1")
    )
    db_save_handler.add_save(
        _save_for(rom, admin_user, "Game [pcsx2 b].saves.zip", "pcsx2", "h2")
    )
    db_save_handler.add_save(_save_for(rom, admin_user, "loose.mcr", "pcsx2", "h3"))
    db_save_handler.add_save(
        _save_for(rom, admin_user, "Game [dolphin].saves.zip", "dolphin", "h4")
    )
    container = {**_container_for(rom), "label": "PCSX2"}
    with (
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"zip-bytes"),
        ),
        patch("endpoints.streaming._push_save_archive", return_value=True) as push,
    ):
        ok = asyncio.run(
            streaming._hydrate_saves_to_broker(admin_user.id, rom.id, container)
        )
    assert ok is True
    push.assert_called_once()
    # The pushed file must be a pcsx2 .zip, never the .mcr or the dolphin save.
    pushed_content = push.call_args[0][1]
    assert pushed_content == b"zip-bytes"


def test_hydrate_saves_no_matching_save_returns_false(rom: Rom, admin_user: User):
    """No stored zip save for the emulator means nothing to hydrate."""
    db_save_handler.add_save(_save_for(rom, admin_user, "loose.mcr", "pcsx2", "h1"))
    container = {**_container_for(rom), "label": "PCSX2"}
    with patch("endpoints.streaming._push_save_archive", return_value=True) as push:
        ok = asyncio.run(
            streaming._hydrate_saves_to_broker(admin_user.id, rom.id, container)
        )
    assert ok is False
    push.assert_not_called()


def test_claim_hydrates_saves_before_launch(client, access_token, rom: Rom):
    """Claiming a session must push stored in-game saves to the container before
    the broker launch (games read saves at boot)."""
    call_order = []
    with _streaming(_container_for(rom)):
        with (
            patch(
                "endpoints.streaming._call_broker",
                side_effect=lambda *a, **k: call_order.append("launch"),
            ),
            patch(
                "endpoints.streaming._hydrate_saves_to_broker",
                new=AsyncMock(side_effect=lambda *a, **k: call_order.append("saves")),
            ) as hydrate_saves,
            patch("endpoints.streaming._spawn_sync_task"),
            patch("endpoints.streaming._hydrate_states_to_broker", new=MagicMock()),
        ):
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    hydrate_saves.assert_awaited_once()
    assert call_order == ["saves", "launch"]


def test_release_spawns_saves_pull(client, access_token, rom: Rom):
    """Releasing a session must schedule a background pull of in-game saves."""
    with _streaming(_container_for(rom)):
        _claim_ok(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._stop_broker"),
            patch("endpoints.streaming._spawn_sync_task") as spawn,
            patch(
                "endpoints.streaming._pull_saves_to_library", new=MagicMock()
            ) as pull,
        ):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers=_auth(access_token),
            )
    assert r.status_code == 200
    spawn.assert_called_once()
    assert pull.call_args[0][1] == rom.id


# ── Resume-from-state ─────────────────────────────────────────────────────────


def test_slot_from_state_filename():
    assert streaming._slot_from_state_filename("pcsx2", "SLUS (A1B2).3.p2s") == 3
    assert streaming._slot_from_state_filename("pcsx2", "SLUS (A1B2).10.p2s") == 10
    assert streaming._slot_from_state_filename("dolphin", "GALE01.s02") == 2
    assert streaming._slot_from_state_filename("pcsx2", "Game.p2s") is None
    assert streaming._slot_from_state_filename("dolphin", "GALE01.gci") is None
    assert streaming._slot_from_state_filename("pcsx2", "Game.0.p2s") is None
    assert streaming._slot_from_state_filename("retroarch", "Game.state") is None


def _resume_claim(client, token, rom, state_id, push_ok=True):
    """Claim with a resume state and full launch-path mocks. Returns
    (response, push mock, call_broker mock, hydrate mock)."""
    container = {**_container_for(rom), "label": "PCSX2"}
    with _streaming(container):
        with (
            patch("endpoints.streaming._call_broker") as call_broker,
            patch("endpoints.streaming._push_state_file", return_value=push_ok) as push,
            patch(
                "endpoints.streaming.fs_asset_handler.read_file",
                new=AsyncMock(return_value=b"state-bytes"),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
            patch(
                "endpoints.streaming._hydrate_states_to_broker", new=MagicMock()
            ) as hydrate,
        ):
            r = _claim(client, token, rom.id, state_id=state_id)
    return r, push, call_broker, hydrate


def test_claim_with_own_state_pushes_file_and_slot(
    client, access_token, rom: Rom, admin_user: User
):
    """A picked state is pushed before launch and its slot rides the launch
    call; hydration must skip that filename so it cannot be overwritten."""
    state = db_state_handler.add_state(
        _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    )
    r, push, call_broker, hydrate = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 200
    assert r.json()["resume"] is True
    push.assert_called_once()
    assert push.call_args[0][1] == "Game.03.p2s"
    assert push.call_args[0][2] == b"state-bytes"
    assert call_broker.call_args[0][3] == 3
    assert hydrate.call_args.kwargs["resume_pushed"] is True


def test_claim_with_other_users_public_state_allowed(
    client, access_token, rom: Rom, viewer_user: User
):
    """Resuming from another user's shared state is the sharing feature."""
    shared = _state_for(rom, viewer_user, "Game.02.p2s", "pcsx2")
    shared.is_public = True
    state = db_state_handler.add_state(shared)
    r, push, call_broker, _ = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 200
    assert r.json()["resume"] is True
    assert call_broker.call_args[0][3] == 2


def test_claim_with_other_users_private_state_404(
    client, access_token, rom: Rom, viewer_user: User
):
    """Another user's private state is invisible - same as nonexistent."""
    state = db_state_handler.add_state(
        _state_for(rom, viewer_user, "Game.02.p2s", "pcsx2")
    )
    r, _, _, _ = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 404
    # The rejected pick must not have claimed the container.
    with _streaming(_container_for(rom)):
        assert _claim_ok(client, access_token, rom.id).status_code == 200


def test_claim_with_wrong_emulator_state_400(
    client, access_token, rom: Rom, admin_user: User
):
    state = db_state_handler.add_state(
        _state_for(rom, admin_user, "Game.state", "retroarch")
    )
    r, _, _, _ = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 400


def test_claim_with_unparseable_slot_400(
    client, access_token, rom: Rom, admin_user: User
):
    state = db_state_handler.add_state(_state_for(rom, admin_user, "Game.p2s", "pcsx2"))
    r, _, _, _ = _resume_claim(client, access_token, rom, state.id)
    assert r.status_code == 400


def test_claim_failed_push_launches_fresh(
    client, access_token, rom: Rom, admin_user: User
):
    """A push failure must not block the session: launch without load_slot
    and report resume=false so the player can tell the user."""
    state = db_state_handler.add_state(
        _state_for(rom, admin_user, "Game.03.p2s", "pcsx2")
    )
    r, _, call_broker, hydrate = _resume_claim(
        client, access_token, rom, state.id, push_ok=False
    )
    assert r.status_code == 200
    assert r.json()["resume"] is False
    assert call_broker.call_args[0][3] is None
    assert hydrate.call_args.kwargs["resume_pushed"] is False


def test_claim_without_state_reports_no_resume(client, access_token, rom: Rom):
    with _streaming(_container_for(rom)):
        r = _claim_ok(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["resume"] is None


# ── Auth guards ───────────────────────────────────────────────────────────────


def test_claim_session_requires_auth(client):
    assert client.post("/api/streaming/sessions", json={"rom_id": 1}).status_code == 403


def test_release_session_requires_auth(client):
    assert client.delete("/api/streaming/sessions/ps2").status_code == 403


def test_force_release_all_requires_auth(client):
    assert client.delete("/api/streaming/sessions").status_code == 403


def test_list_sessions_requires_auth(client):
    assert client.get("/api/streaming/sessions").status_code == 403


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
        with patch("endpoints.streaming._stop_broker") as stop:
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


def _mc_claim(client, token, rom_id, memory_card_id=None):
    body = {"rom_id": rom_id}
    if memory_card_id is not None:
        body["memory_card_id"] = memory_card_id
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
    resolved = streaming._resolve_memory_card(admin_user.id, "pcsx2", card.id)
    assert resolved is not None
    assert resolved.id == card.id


def test_resolve_memory_card_wrong_emulator_404(admin_user: User):
    card = _make_card(admin_user, emulator="dolphin")
    with pytest.raises(HTTPException) as exc:
        streaming._resolve_memory_card(admin_user.id, "pcsx2", card.id)
    assert exc.value.status_code == 404


def test_resolve_memory_card_foreign_id_404(admin_user: User, viewer_user: User):
    """An id owned by another user is not resolvable, even if public."""
    card = _make_card(viewer_user, is_public=True)
    with pytest.raises(HTTPException) as exc:
        streaming._resolve_memory_card(admin_user.id, "pcsx2", card.id)
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
    resolved = streaming._resolve_memory_card(admin_user.id, "pcsx2", None)
    assert resolved is not None
    assert resolved.id == newer.id


def test_resolve_memory_card_none_when_user_has_no_card(admin_user: User):
    """Resolution never creates rows; a cardless user resolves to None so the
    claim path can defer creation until the claim is won."""
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []
    assert streaming._resolve_memory_card(admin_user.id, "pcsx2", None) is None
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_create_blank_memory_card(admin_user: User, rom: Rom):
    """First play on an emulator with no card creates a blank owned card."""
    created = streaming._create_blank_memory_card(
        admin_user.id, "pcsx2", rom.platform_id
    )
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
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(return_value=b"card-bytes"),
        ),
        patch("endpoints.streaming._push_memory_card", return_value=True) as push,
    ):
        ok = asyncio.run(
            streaming._hydrate_memory_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == b"card-bytes"


def test_hydrate_blank_card_wipes_container(admin_user: User, rom: Rom):
    """A card with no version pushes the empty zip so the container is wiped."""
    card = _make_card(admin_user)
    with patch("endpoints.streaming._push_memory_card", return_value=True) as push:
        ok = asyncio.run(
            streaming._hydrate_memory_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == streaming._EMPTY_MEMORY_CARD


def test_hydrate_missing_file_wipes_to_blank(admin_user: User, rom: Rom):
    """A version row whose file is gone must wipe to blank, never leak."""
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(card.id, "My PS2 card [gone].card.zip", "h1")
    )
    with (
        patch(
            "endpoints.streaming.fs_asset_handler.read_file",
            new=AsyncMock(side_effect=FileNotFoundError),
        ),
        patch("endpoints.streaming._push_memory_card", return_value=True) as push,
    ):
        ok = asyncio.run(
            streaming._hydrate_memory_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is True
    assert push.call_args[0][1] == streaming._EMPTY_MEMORY_CARD


def test_hydrate_returns_false_on_push_failure(admin_user: User, rom: Rom):
    card = _make_card(admin_user)
    with patch("endpoints.streaming._push_memory_card", return_value=False):
        ok = asyncio.run(
            streaming._hydrate_memory_card_to_broker(
                admin_user.id, card, _mc_container_for(rom)
            )
        )
    assert ok is False


def test_store_memory_card_version_stores_new(admin_user: User):
    card = _make_card(admin_user)
    scanned = _card_version(card.id, "My PS2 card [new].card.zip", "hash-new")
    with (
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()) as wf,
        patch(
            "endpoints.streaming.scan_memory_card_version",
            new=AsyncMock(return_value=scanned),
        ),
    ):
        stored = asyncio.run(
            streaming._store_memory_card_version(
                admin_user, card, "pcsx2", b"card-bytes"
            )
        )
    assert stored is True
    wf.assert_awaited_once()
    assert db_memory_card_handler.get_latest_version(card.id).content_hash == "hash-new"


def test_store_memory_card_version_dedups_identical(admin_user: User):
    card = _make_card(admin_user)
    db_memory_card_handler.add_version(
        _card_version(card.id, "My PS2 card [old].card.zip", "dup")
    )
    scanned = _card_version(card.id, "My PS2 card [new].card.zip", "dup")
    with (
        patch("endpoints.streaming.fs_asset_handler.write_file", new=AsyncMock()),
        patch(
            "endpoints.streaming.scan_memory_card_version",
            new=AsyncMock(return_value=scanned),
        ),
        patch(
            "endpoints.streaming.fs_asset_handler.remove_file", new=AsyncMock()
        ) as rm,
    ):
        stored = asyncio.run(
            streaming._store_memory_card_version(
                admin_user, card, "pcsx2", b"card-bytes"
            )
        )
    assert stored is False
    rm.assert_awaited_once()
    assert len(db_memory_card_handler.get_versions(card.id)) == 1


def test_evacuate_memory_card_stores_snapshot(admin_user: User, rom: Rom):
    card = _make_card(admin_user)
    with (
        patch("endpoints.streaming._fetch_memory_card", return_value=b"card-bytes"),
        patch(
            "endpoints.streaming._store_memory_card_version",
            new=AsyncMock(return_value=True),
        ) as store,
    ):
        ok = asyncio.run(
            streaming._evacuate_memory_card(
                admin_user.id, card.id, "pcsx2", _mc_container_for(rom)
            )
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
        patch("endpoints.streaming._fetch_memory_card", return_value=None),
        patch(
            "endpoints.streaming._store_memory_card_version", new=AsyncMock()
        ) as store,
    ):
        ok = asyncio.run(
            streaming._evacuate_memory_card(
                admin_user.id, card.id, "pcsx2", _mc_container_for(rom)
            )
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
            "endpoints.streaming._fetch_memory_card",
            side_effect=streaming._MemoryCardUnavailable("boom"),
        ),
        patch(
            "endpoints.streaming._store_memory_card_version", new=AsyncMock()
        ) as store,
    ):
        ok = asyncio.run(
            streaming._evacuate_memory_card(
                admin_user.id, card.id, "pcsx2", _mc_container_for(rom)
            )
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


def test_fetch_memory_card_returns_bytes(rom: Rom):
    resp = MagicMock()
    resp.__enter__.return_value.read.return_value = b"card-bytes"
    with patch("endpoints.streaming.urllib.request.urlopen", return_value=resp):
        assert streaming._fetch_memory_card(_mc_container_for(rom)) == b"card-bytes"


def test_fetch_memory_card_absent_header_returns_none(rom: Rom):
    """A 404 tagged X-Memory-Card: absent means the slot is genuinely empty."""
    with patch(
        "endpoints.streaming.urllib.request.urlopen",
        side_effect=_http_error(404, {"X-Memory-Card": "absent"}),
    ):
        assert streaming._fetch_memory_card(_mc_container_for(rom)) is None


def test_fetch_memory_card_unmarked_404_raises(rom: Rom):
    """An untagged 404 (endpoint missing on an old broker) must NOT be mistaken
    for an empty slot; it raises so the card is never wiped."""
    with patch(
        "endpoints.streaming.urllib.request.urlopen", side_effect=_http_error(404)
    ):
        with pytest.raises(streaming._MemoryCardUnavailable):
            streaming._fetch_memory_card(_mc_container_for(rom))


def test_fetch_memory_card_file_card_409_raises(rom: Rom):
    with patch(
        "endpoints.streaming.urllib.request.urlopen", side_effect=_http_error(409)
    ):
        with pytest.raises(streaming._MemoryCardUnavailable):
            streaming._fetch_memory_card(_mc_container_for(rom))


def test_fetch_memory_card_transport_error_raises(rom: Rom):
    import urllib.error

    with patch(
        "endpoints.streaming.urllib.request.urlopen",
        side_effect=urllib.error.URLError("broker down"),
    ):
        with pytest.raises(streaming._MemoryCardUnavailable):
            streaming._fetch_memory_card(_mc_container_for(rom))


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
            patch("endpoints.streaming._call_broker", side_effect=_note_launch),
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(side_effect=_note_card),
            ) as hydrate_card,
            patch(
                "endpoints.streaming._hydrate_saves_to_broker", new=AsyncMock()
            ) as legacy,
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 200
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
            patch("endpoints.streaming._call_broker") as launch,
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(return_value=False),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            r = _mc_claim(client, access_token, rom.id)
    assert r.status_code == 502
    launch.assert_not_called()
    # The claim must be released so the container is not wedged.
    assert (
        asyncio.run(
            streaming._get_session(streaming._container_key(_mc_container_for(rom)))
        )
        is None
    )
    # No orphan blank card survives the aborted claim.
    assert db_memory_card_handler.get_cards(admin_user.id, "pcsx2") == []


def test_save_and_exit_evacuates_card(client, access_token, rom: Rom):
    with _streaming(_mc_container_for(rom)):
        with (
            patch("endpoints.streaming._call_broker"),
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._save_and_exit_broker", return_value=(True, 1)),
            patch(
                "endpoints.streaming._evacuate_memory_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch("endpoints.streaming._wipe_session_card", new=AsyncMock()) as wipe,
            patch("endpoints.streaming._pull_saves_to_library") as legacy,
            patch("endpoints.streaming._spawn_sync_task"),
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
            patch("endpoints.streaming._call_broker"),
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            patch("endpoints.streaming._stop_broker") as stop,
            patch(
                "endpoints.streaming._evacuate_memory_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch("endpoints.streaming._wipe_session_card", new=AsyncMock()) as wipe,
            patch("endpoints.streaming._spawn_sync_task") as spawn,
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


def test_save_and_exit_wait_false_forces_blocking_on_card_sync(
    client, access_token, rom: Rom
):
    """Whole-card sync must quiesce the emulator before evacuating, so a
    wait=false request still runs a blocking save+kill."""
    with _streaming(_mc_container_for(rom)):
        with (
            patch("endpoints.streaming._call_broker"),
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            _mc_claim(client, access_token, rom.id)
        with (
            patch(
                "endpoints.streaming._save_and_exit_broker", return_value=(True, 1)
            ) as save,
            patch(
                "endpoints.streaming._evacuate_memory_card",
                new=AsyncMock(return_value=True),
            ) as evac,
            patch("endpoints.streaming._wipe_session_card", new=AsyncMock()),
            patch("endpoints.streaming._spawn_sync_task"),
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
            patch("endpoints.streaming._call_broker"),
            patch(
                "endpoints.streaming._hydrate_memory_card_to_broker",
                new=AsyncMock(return_value=True),
            ),
            patch("endpoints.streaming._spawn_sync_task"),
        ):
            assert _mc_claim(client, access_token, rom.id).status_code == 200
            assert db_memory_card_handler.get_cards(viewer_user.id, "pcsx2") == []
            r = _mc_claim(client, viewer_access_token, rom.id)
    assert r.status_code == 409
    assert db_memory_card_handler.get_cards(viewer_user.id, "pcsx2") == []


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
    asyncio.run(streaming._record_play_session(session))

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
    asyncio.run(streaming._record_play_session(session))
    assert db_play_session_handler.get_total_play_time(admin_user.id, rom.id) == 0


def test_record_play_session_ignores_malformed_session(admin_user: User, rom: Rom):
    """Missing rom_id / claimed_at must be a no-op, never an error."""
    asyncio.run(streaming._record_play_session({"user_id": admin_user.id}))
    asyncio.run(
        streaming._record_play_session(
            {"user_id": admin_user.id, "rom_id": rom.id, "claimed_at": "not-a-date"}
        )
    )
    assert db_play_session_handler.get_total_play_time(admin_user.id, rom.id) == 0
