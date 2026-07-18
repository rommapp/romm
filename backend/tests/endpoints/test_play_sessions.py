import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_device_handler, db_play_session_handler, db_rom_handler
from models.device import Device
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils.datetime import to_utc


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def editor_access_token(editor_user: User):
    return oauth_handler.create_access_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


@pytest.fixture
def device(admin_user: User):
    return db_device_handler.add_device(
        Device(
            id=str(uuid.uuid4()),
            user_id=admin_user.id,
            name="Test Device",
            platform="android",
        )
    )


def _session(
    rom_id=None,
    save_slot=None,
    start_offset_hours=-1,
    duration_minutes=30,
):
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=start_offset_hours)
    end = start + timedelta(minutes=duration_minutes)
    return {
        "rom_id": rom_id,
        "save_slot": save_slot,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_ms": duration_minutes * 60 * 1000,
    }


def _ingest(device_id=None, sessions=None):
    return {"device_id": device_id, "sessions": sessions or []}


class TestPlaySessionIngest:
    def test_single_session(self, client, access_token: str, device: Device, rom: Rom):
        payload = _ingest(device_id=device.id, sessions=[_session(rom_id=rom.id)])
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["created_count"] == 1
        assert data["skipped_count"] == 0
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "created"
        assert data["results"][0]["id"] is not None

    def test_batch_sessions(self, client, access_token: str, device: Device, rom: Rom):
        payload = _ingest(
            device_id=device.id,
            sessions=[
                _session(rom_id=rom.id, start_offset_hours=-i) for i in range(1, 6)
            ],
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["created_count"] == 5
        assert data["skipped_count"] == 0

    def test_validation_end_before_start(self, client, access_token: str):
        now = datetime.now(timezone.utc)
        payload = _ingest(
            sessions=[
                {
                    "start_time": now.isoformat(),
                    "end_time": (now - timedelta(hours=1)).isoformat(),
                    "duration_ms": 1000,
                }
            ]
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_validation_negative_duration(self, client, access_token: str):
        now = datetime.now(timezone.utc)
        payload = _ingest(
            sessions=[
                {
                    "start_time": now.isoformat(),
                    "end_time": (now + timedelta(hours=1)).isoformat(),
                    "duration_ms": -1,
                }
            ]
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_future_end_time_rejected(self, client, access_token: str):
        now = datetime.now(timezone.utc)
        payload = _ingest(
            sessions=[
                {
                    "start_time": now.isoformat(),
                    "end_time": (now + timedelta(hours=1)).isoformat(),
                    "duration_ms": 1000,
                }
            ]
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["results"][0]["status"] == "error"
        assert data["skipped_count"] == 1

    def test_empty_batch(self, client, access_token: str):
        response = client.post(
            "/api/play-sessions",
            json=_ingest(),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_batch_exceeds_max(self, client, access_token: str):
        payload = _ingest(
            sessions=[_session(start_offset_hours=-i) for i in range(1, 102)]
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_zero_duration_accepted(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        now = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = _ingest(
            device_id=device.id,
            sessions=[
                {
                    "rom_id": rom.id,
                    "start_time": now.isoformat(),
                    "end_time": (now + timedelta(seconds=5)).isoformat(),
                    "duration_ms": 0,
                }
            ],
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["created_count"] == 1


class TestPlaySessionDedup:
    def test_duplicate_batch(self, client, access_token: str, device: Device, rom: Rom):
        payload = _ingest(device_id=device.id, sessions=[_session(rom_id=rom.id)])

        response1 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.json()["created_count"] == 1

        response2 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response2.status_code == status.HTTP_201_CREATED
        data = response2.json()
        assert data["created_count"] == 0
        assert data["skipped_count"] == 1
        assert data["results"][0]["status"] == "duplicate"

    def test_mixed_new_and_duplicate(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        first_session = _session(rom_id=rom.id, start_offset_hours=-2)
        client.post(
            "/api/play-sessions",
            json=_ingest(device_id=device.id, sessions=[first_session]),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        mixed = _ingest(
            device_id=device.id,
            sessions=[
                first_session,
                _session(rom_id=rom.id, start_offset_hours=-3),
            ],
        )
        response = client.post(
            "/api/play-sessions",
            json=mixed,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        data = response.json()
        assert data["created_count"] == 1
        assert data["skipped_count"] == 1

    def test_dedup_with_null_device_and_rom(self, client, access_token: str):
        now = datetime.now(timezone.utc) - timedelta(hours=5)
        payload = _ingest(
            sessions=[
                {
                    "start_time": now.isoformat(),
                    "end_time": (now + timedelta(minutes=30)).isoformat(),
                    "duration_ms": 1800000,
                }
            ]
        )

        resp1 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp1.json()["created_count"] == 1

        resp2 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp2.json()["skipped_count"] == 1
        assert resp2.json()["created_count"] == 0

    def test_cross_user_same_session_no_collision(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        device: Device,
        rom: Rom,
    ):
        payload = _ingest(sessions=[_session(rom_id=rom.id, start_offset_hours=-6)])

        resp1 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp1.json()["created_count"] == 1

        resp2 = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert resp2.json()["created_count"] == 1


class TestPlaySessionLenientIngest:
    def test_unknown_device_id(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        payload = _ingest(
            device_id="nonexistent-device", sessions=[_session(rom_id=rom.id)]
        )
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["created_count"] == 1

        sessions = db_play_session_handler.get_sessions(
            user_id=admin_user.id, rom_id=rom.id
        )
        assert len(sessions) == 1
        assert sessions[0].device_id is None

    def test_unknown_rom_id(self, client, access_token: str, device: Device):
        payload = _ingest(device_id=device.id, sessions=[_session(rom_id=999999)])
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["created_count"] == 1

    def test_no_device_no_game(self, client, access_token: str):
        payload = _ingest(sessions=[_session()])
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["created_count"] == 1


class TestPlaySessionUserIsolation:
    def test_other_users_device_nullified(
        self,
        client,
        editor_access_token: str,
        device: Device,
        rom: Rom,
    ):
        payload = _ingest(device_id=device.id, sessions=[_session(rom_id=rom.id)])
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["created_count"] == 1

    def test_get_only_own_sessions(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        admin_user: User,
        editor_user: User,
        rom: Rom,
    ):
        client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session(rom_id=rom.id, start_offset_hours=-1)]),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session(rom_id=rom.id, start_offset_hours=-2)]),
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        response = client.get(
            "/api/play-sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(s["user_id"] == admin_user.id for s in data)

    def test_delete_other_users_session(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        admin_user: User,
    ):
        resp = client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session()]),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        session_id = resp.json()["results"][0]["id"]

        response = client.delete(
            f"/api/play-sessions/{session_id}",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPlaySessionRomUserUpdates:
    def test_last_played_updated(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        payload = _ingest(sessions=[_session(rom_id=rom.id)])
        response = client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=admin_user.id)
        assert rom_user is not None
        assert rom_user.last_played is not None

    def test_last_played_is_max_end_time(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=3)
        later = now - timedelta(hours=1)

        payload = _ingest(
            sessions=[
                {
                    "rom_id": rom.id,
                    "start_time": earlier.isoformat(),
                    "end_time": (earlier + timedelta(minutes=30)).isoformat(),
                    "duration_ms": 1800000,
                },
                {
                    "rom_id": rom.id,
                    "start_time": later.isoformat(),
                    "end_time": (later + timedelta(minutes=30)).isoformat(),
                    "duration_ms": 1800000,
                },
            ]
        )
        client.post(
            "/api/play-sessions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=admin_user.id)
        expected_latest = later + timedelta(minutes=30)
        last_played_utc = to_utc(rom_user.last_played)
        assert abs((last_played_utc - expected_latest).total_seconds()) < 2

    def test_rom_user_created_if_not_exists(
        self, client, access_token: str, admin_user: User, platform: Platform
    ):
        new_rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="new_rom",
                slug="new_rom_slug",
                fs_name="new_rom.zip",
                fs_name_no_tags="new_rom",
                fs_name_no_ext="new_rom",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )

        assert (
            db_rom_handler.get_rom_user(rom_id=new_rom.id, user_id=admin_user.id)
            is None
        )

        client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session(rom_id=new_rom.id)]),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        rom_user = db_rom_handler.get_rom_user(rom_id=new_rom.id, user_id=admin_user.id)
        assert rom_user is not None
        assert rom_user.last_played is not None


class TestPlaySessionQuery:
    def test_filter_by_rom_id(
        self, client, access_token: str, rom: Rom, platform: Platform
    ):
        other_rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="other_rom",
                slug="other_rom_slug",
                fs_name="other_rom.zip",
                fs_name_no_tags="other_rom",
                fs_name_no_ext="other_rom",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )

        client.post(
            "/api/play-sessions",
            json=_ingest(
                sessions=[
                    _session(rom_id=rom.id, start_offset_hours=-1),
                    _session(rom_id=other_rom.id, start_offset_hours=-2),
                ]
            ),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            f"/api/play-sessions?rom_id={rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["rom_id"] == rom.id

    def test_filter_by_device_id(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        client.post(
            "/api/play-sessions",
            json=_ingest(
                device_id=device.id,
                sessions=[_session(rom_id=rom.id, start_offset_hours=-1)],
            ),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session(rom_id=rom.id, start_offset_hours=-2)]),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            f"/api/play-sessions?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["device_id"] == device.id

    def test_pagination(self, client, access_token: str, rom: Rom):
        client.post(
            "/api/play-sessions",
            json=_ingest(
                sessions=[
                    _session(rom_id=rom.id, start_offset_hours=-i) for i in range(1, 6)
                ]
            ),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            "/api/play-sessions?limit=2&offset=0",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

        response2 = client.get(
            "/api/play-sessions?limit=2&offset=2",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 2

    def test_filter_by_time_range(self, client, access_token: str, rom: Rom):
        now = datetime.now(timezone.utc)
        client.post(
            "/api/play-sessions",
            json=_ingest(
                sessions=[
                    _session(rom_id=rom.id, start_offset_hours=-24),
                    _session(rom_id=rom.id, start_offset_hours=-12),
                    _session(rom_id=rom.id, start_offset_hours=-1),
                ]
            ),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            "/api/play-sessions",
            params={
                "start_after": (now - timedelta(hours=18)).isoformat(),
                "end_before": (now - timedelta(hours=2)).isoformat(),
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

    def test_time_range_ignores_limit(self, client, access_token: str, rom: Rom):
        now = datetime.now(timezone.utc)
        client.post(
            "/api/play-sessions",
            json=_ingest(
                sessions=[
                    _session(rom_id=rom.id, start_offset_hours=-i) for i in range(1, 6)
                ]
            ),
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            "/api/play-sessions",
            params={
                "start_after": (now - timedelta(hours=10)).isoformat(),
                "limit": 2,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 5


class TestPlaySessionDelete:
    def test_delete_own_session(self, client, access_token: str):
        resp = client.post(
            "/api/play-sessions",
            json=_ingest(sessions=[_session()]),
            headers={"Authorization": f"Bearer {access_token}"},
        )
        session_id = resp.json()["results"][0]["id"]

        response = client.delete(
            f"/api/play-sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_nonexistent(self, client, access_token: str):
        response = client.delete(
            "/api/play-sessions/999999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
