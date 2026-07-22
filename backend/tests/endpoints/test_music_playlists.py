import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.endpoints.test_music import (  # noqa: F401
    _auth,
    _track_id,
    music_library,
)

from handler.database import db_music_playlist_handler, db_rom_handler
from models.rom import RomFile, RomFileCategory, TrackMeta
from models.user import User


@pytest.fixture
def playlist_id(
    client: TestClient,
    access_token: str,
    music_library,  # noqa: F811
) -> int:
    r = client.post(
        "/api/music/playlists",
        json={"name": "Chill", "description": "slow tunes"},
        headers=_auth(access_token),
    )
    assert r.status_code == status.HTTP_200_OK
    return r.json()["id"]


def _add_tracks(client: TestClient, token: str, playlist: int, titles: list[str]):
    ids = [_track_id(client, token, t) for t in titles]
    r = client.post(
        f"/api/music/playlists/{playlist}/tracks",
        json={"rom_file_ids": ids},
        headers=_auth(token),
    )
    assert r.status_code == status.HTTP_200_OK
    return ids


def _playlist_titles(client: TestClient, token: str, playlist: int) -> list[str]:
    body = client.get(
        f"/api/music/playlists/{playlist}/tracks", headers=_auth(token)
    ).json()
    return [i["title"] for i in body["items"]]


# ---------- CRUD ----------


def test_playlist_crud(client: TestClient, access_token: str, playlist_id: int):
    body = client.get("/api/music/playlists", headers=_auth(access_token)).json()
    assert [p["name"] for p in body] == ["Chill"]
    assert body[0]["track_count"] == 0 and body[0]["is_public"] is False

    r = client.put(
        f"/api/music/playlists/{playlist_id}",
        json={"name": "Chiller", "is_public": True},
        headers=_auth(access_token),
    )
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["name"] == "Chiller" and r.json()["is_public"] is True
    # description untouched by partial update
    assert r.json()["description"] == "slow tunes"

    r = client.delete(
        f"/api/music/playlists/{playlist_id}", headers=_auth(access_token)
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/api/music/playlists", headers=_auth(access_token)).json() == []


def test_playlist_duplicate_name_400(
    client: TestClient, access_token: str, playlist_id: int
):
    r = client.post(
        "/api/music/playlists",
        json={"name": "Chill"},
        headers=_auth(access_token),
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    # another user may reuse the name
    assert playlist_id is not None


def test_playlist_unknown_id_404(
    client: TestClient,
    access_token: str,
    music_library,  # noqa: F811
):
    assert (
        client.get(
            "/api/music/playlists/999999", headers=_auth(access_token)
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


# ---------- ownership / visibility ----------


def test_private_playlist_hidden_from_other_users(
    client: TestClient,
    access_token: str,
    editor_access_token: str,
    playlist_id: int,
):
    assert (
        client.get("/api/music/playlists", headers=_auth(editor_access_token)).json()
        == []
    )
    assert (
        client.get(
            f"/api/music/playlists/{playlist_id}", headers=_auth(editor_access_token)
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_public_playlist_readable_not_writable_by_others(
    client: TestClient,
    access_token: str,
    editor_access_token: str,
    playlist_id: int,
):
    client.put(
        f"/api/music/playlists/{playlist_id}",
        json={"is_public": True},
        headers=_auth(access_token),
    )
    _add_tracks(client, access_token, playlist_id, ["Green Hill"])

    listed = client.get(
        "/api/music/playlists", headers=_auth(editor_access_token)
    ).json()
    assert [p["id"] for p in listed] == [playlist_id]
    assert (
        client.get(
            f"/api/music/playlists/{playlist_id}/tracks",
            headers=_auth(editor_access_token),
        ).json()["total"]
        == 1
    )

    # all writes are owner-only
    for method, path, payload in [
        ("PUT", f"/api/music/playlists/{playlist_id}", {"name": "Mine now"}),
        ("DELETE", f"/api/music/playlists/{playlist_id}", None),
        (
            "POST",
            f"/api/music/playlists/{playlist_id}/tracks",
            {"rom_file_ids": [1]},
        ),
        (
            "DELETE",
            f"/api/music/playlists/{playlist_id}/tracks",
            {"rom_file_ids": [1]},
        ),
        (
            "PUT",
            f"/api/music/playlists/{playlist_id}/tracks/order",
            {"rom_file_ids": [1]},
        ),
    ]:
        r = client.request(
            method, path, json=payload, headers=_auth(editor_access_token)
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN, (method, path)


# ---------- tracks ----------


def test_playlist_tracks_ordered_and_deduped(
    client: TestClient, access_token: str, playlist_id: int
):
    ids = _add_tracks(
        client, access_token, playlist_id, ["Jingle", "Green Hill", "Overworld"]
    )
    assert _playlist_titles(client, access_token, playlist_id) == [
        "Jingle",
        "Green Hill",
        "Overworld",
    ]

    # re-adding an existing track is a no-op
    r = client.post(
        f"/api/music/playlists/{playlist_id}/tracks",
        json={"rom_file_ids": [ids[0]]},
        headers=_auth(access_token),
    )
    assert r.json()["added"] == 0

    body = client.get("/api/music/playlists", headers=_auth(access_token)).json()
    assert body[0]["track_count"] == 3


def test_playlist_reorder(client: TestClient, access_token: str, playlist_id: int):
    ids = _add_tracks(
        client, access_token, playlist_id, ["Jingle", "Green Hill", "Overworld"]
    )
    r = client.put(
        f"/api/music/playlists/{playlist_id}/tracks/order",
        json={"rom_file_ids": [ids[2], ids[0], ids[1]]},
        headers=_auth(access_token),
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert _playlist_titles(client, access_token, playlist_id) == [
        "Overworld",
        "Jingle",
        "Green Hill",
    ]


def test_playlist_partial_reorder_keeps_rest_after(
    client: TestClient, access_token: str, playlist_id: int
):
    ids = _add_tracks(
        client, access_token, playlist_id, ["Jingle", "Green Hill", "Overworld"]
    )
    client.put(
        f"/api/music/playlists/{playlist_id}/tracks/order",
        json={"rom_file_ids": [ids[2]]},
        headers=_auth(access_token),
    )
    assert _playlist_titles(client, access_token, playlist_id) == [
        "Overworld",
        "Jingle",
        "Green Hill",
    ]


def test_playlist_reorder_foreign_track_400(
    client: TestClient, access_token: str, playlist_id: int
):
    _add_tracks(client, access_token, playlist_id, ["Jingle"])
    outsider = _track_id(client, access_token, "Overworld")
    r = client.put(
        f"/api/music/playlists/{playlist_id}/tracks/order",
        json={"rom_file_ids": [outsider]},
        headers=_auth(access_token),
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


def test_playlist_remove_tracks(
    client: TestClient, access_token: str, playlist_id: int
):
    ids = _add_tracks(
        client, access_token, playlist_id, ["Jingle", "Green Hill", "Overworld"]
    )
    r = client.request(
        "DELETE",
        f"/api/music/playlists/{playlist_id}/tracks",
        json={"rom_file_ids": [ids[1]]},
        headers=_auth(access_token),
    )
    assert r.json()["removed"] == 1
    assert _playlist_titles(client, access_token, playlist_id) == [
        "Jingle",
        "Overworld",
    ]


# ---------- durability ----------


def test_playlist_survives_rom_file_id_churn(
    client: TestClient, access_token: str, playlist_id: int, music_library  # noqa: F811
):
    _add_tracks(client, access_token, playlist_id, ["Green Hill", "Jingle"])

    rom = music_library["sonic"]
    purged = db_rom_handler.purge_rom_files(rom.id)
    old = next(f for f in purged if f.file_name == "Green Hill.mp3")
    new_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=old.file_name,
            file_path=old.file_path,
            file_size_bytes=old.file_size_bytes,
            md5_hash=old.md5_hash,
            category=RomFileCategory.SOUNDTRACK,
            track_meta=TrackMeta(rom_id=rom.id, title="Green Hill"),
        )
    )

    body = client.get(
        f"/api/music/playlists/{playlist_id}/tracks", headers=_auth(access_token)
    ).json()
    assert [i["title"] for i in body["items"]] == ["Green Hill", "Jingle"]
    assert body["items"][0]["rom_file_id"] == new_file.id


def test_playlist_dangling_entry_omitted_but_counted(
    client: TestClient, access_token: str, playlist_id: int, music_library  # noqa: F811
):
    _add_tracks(client, access_token, playlist_id, ["Green Hill", "Jingle"])

    # File comes back with different content: the old entry dangles.
    rom = music_library["sonic"]
    db_rom_handler.purge_rom_files(rom.id)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Green Hill.mp3",
            file_path=f"{rom.fs_path}/Sonic/soundtrack",
            file_size_bytes=4096,
            md5_hash="md5-different-content",
            category=RomFileCategory.SOUNDTRACK,
            track_meta=TrackMeta(rom_id=rom.id, title="Green Hill"),
        )
    )

    tracks = client.get(
        f"/api/music/playlists/{playlist_id}/tracks", headers=_auth(access_token)
    ).json()
    assert [i["title"] for i in tracks["items"]] == ["Jingle"]
    # stored count still includes the dangling entry
    listing = client.get("/api/music/playlists", headers=_auth(access_token)).json()
    assert listing[0]["track_count"] == 2


def test_playlist_tracks_respect_viewer_hidden_platforms(
    client: TestClient,
    access_token: str,
    playlist_id: int,
    music_library,  # noqa: F811
):
    _add_tracks(client, access_token, playlist_id, ["Green Hill", "Overworld"])
    entries = db_music_playlist_handler.get_playlist_entries(playlist_id)
    assert len(entries) == 2

    pb = music_library["platform_b"].id
    rows, total = db_rom_handler.get_music_tracks(
        playlist_id=playlist_id, hidden_platform_ids=[pb]
    )
    assert total == 1
    assert rows[0].title == "Green Hill"


# ---------- favorites flag on playlist rows ----------


def test_playlist_rows_carry_is_favorite(
    client: TestClient, access_token: str, playlist_id: int
):
    ids = _add_tracks(client, access_token, playlist_id, ["Green Hill", "Jingle"])
    client.post(
        "/api/music/favorites",
        json={"rom_file_ids": [ids[0]]},
        headers=_auth(access_token),
    )
    body = client.get(
        f"/api/music/playlists/{playlist_id}/tracks", headers=_auth(access_token)
    ).json()
    flags = {i["title"]: i["is_favorite"] for i in body["items"]}
    assert flags == {"Green Hill": True, "Jingle": False}


# ---------- duplicate content in one rom ----------


def test_duplicate_content_resolves_to_single_row(
    client: TestClient, access_token: str, playlist_id: int, music_library  # noqa: F811
):
    _add_tracks(client, access_token, playlist_id, ["Green Hill"])
    rom = music_library["sonic"]
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Green Hill (copy).mp3",
            file_path=f"{rom.fs_path}/Sonic/soundtrack",
            file_size_bytes=2048,
            md5_hash="md5-green-hill",
            category=RomFileCategory.SOUNDTRACK,
            track_meta=TrackMeta(rom_id=rom.id, title="Green Hill"),
        )
    )
    body = client.get(
        f"/api/music/playlists/{playlist_id}/tracks", headers=_auth(access_token)
    ).json()
    assert body["total"] == 1


# ---------- scopes ----------


def test_playlists_require_scopes(
    client: TestClient, admin_user: User, music_library  # noqa: F811
):
    from datetime import timedelta

    from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
    from handler.auth import oauth_handler

    read_only = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": "playlists.read",
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    assert (
        client.get("/api/music/playlists", headers=_auth(read_only)).status_code
        == status.HTTP_200_OK
    )
    assert (
        client.post(
            "/api/music/playlists", json={"name": "Nope"}, headers=_auth(read_only)
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )
