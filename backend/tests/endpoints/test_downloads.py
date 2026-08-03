from fastapi import status

from handler.database import db_download_handler, db_rom_handler
from models.download_event import DownloadKind, DownloadSource
from models.rom import Rom
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _record(rom: Rom, user: User, **kwargs):
    return db_download_handler.record_download(
        rom=rom,
        user_id=user.id,
        username=user.username,
        source=kwargs.pop("source", DownloadSource.WEBUI),
        kind=kwargs.pop("kind", DownloadKind.ROM),
        file_count=kwargs.pop("file_count", 1),
        size_bytes=kwargs.pop("size_bytes", 1000),
        **kwargs,
    )


def test_overview_requires_auth(client):
    # Unauthenticated is 401; a signed-in caller missing the scope gets 403.
    response = client.get("/api/stats/downloads")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_log_requires_auth(client):
    response = client.get("/api/stats/downloads/log")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_overview_forbidden_without_users_read(client, viewer_access_token):
    # `users.read` is admin-tier; a viewer must not see download stats.
    response = client.get("/api/stats/downloads", headers=_auth(viewer_access_token))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_log_forbidden_without_users_read(client, viewer_access_token):
    # The log carries usernames, IPs and user agents, admin only.
    response = client.get(
        "/api/stats/downloads/log", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_overview_returns_stats_for_admin(
    client, access_token, rom: Rom, admin_user: User
):
    _record(rom, admin_user, size_bytes=2048)

    response = client.get("/api/stats/downloads", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["summary"]["total_downloads"] == 1
    assert body["summary"]["total_bytes"] == 2048
    assert body["top_roms"][0]["rom_id"] == rom.id
    assert body["by_source"][0]["source"] == "webui"
    assert len(body["timeline"]) == 30


def test_overview_honours_window_and_top_limit(
    client, access_token, rom: Rom, admin_user: User
):
    _record(rom, admin_user)

    response = client.get(
        "/api/stats/downloads?days=7&top_limit=1", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body["timeline"]) == 7
    assert len(body["top_roms"]) == 1


def test_overview_rejects_out_of_range_window(client, access_token):
    response = client.get("/api/stats/downloads?days=0", headers=_auth(access_token))
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_log_returns_entries_for_admin(
    client, access_token, rom: Rom, admin_user: User
):
    _record(rom, admin_user, client_ip="10.0.0.9", user_agent="pytest/1.0")

    response = client.get("/api/stats/downloads/log", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["total"] == 1
    entry = body["items"][0]
    assert entry["username"] == admin_user.username
    assert entry["rom_id"] == rom.id
    assert entry["client_ip"] == "10.0.0.9"
    assert entry["user_agent"] == "pytest/1.0"


def test_log_filters_by_source(client, access_token, rom: Rom, admin_user: User):
    _record(rom, admin_user, source=DownloadSource.WEBUI)
    _record(rom, admin_user, source=DownloadSource.CLIENT_TOKEN)

    response = client.get(
        "/api/stats/downloads/log?source=client_token", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["source"] == "client_token"


def test_log_rejects_unknown_source(client, access_token):
    response = client.get(
        "/api/stats/downloads/log?source=carrier-pigeon", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_resync_requires_users_write(client, editor_access_token):
    response = client.post(
        "/api/stats/downloads/resync", headers=_auth(editor_access_token)
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_resync_rebuilds_counters(client, access_token, rom: Rom, admin_user: User):
    _record(rom, admin_user)
    db_rom_handler.update_rom(rom.id, {"download_count": 42})

    response = client.post("/api/stats/downloads/resync", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"roms_with_downloads": 1}

    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.download_count == 1
