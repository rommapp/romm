from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import soundtrack as soundtrack_endpoint
from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory

MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x21fake mp3 payload"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def soundtrack_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    folder_dir = tmp_path / "library"
    folder_dir.mkdir()

    def validate_path(path: str) -> Path:
        return folder_dir / Path(path).name

    async def remove_file(path: str) -> None:
        target = folder_dir / Path(path).name
        if target.exists():
            target.unlink()
        else:
            raise FileNotFoundError(path)

    monkeypatch.setattr(
        soundtrack_endpoint.fs_rom_handler, "validate_path", validate_path
    )
    monkeypatch.setattr(
        soundtrack_endpoint.fs_rom_handler,
        "make_directory",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        soundtrack_endpoint.fs_rom_handler,
        "remove_file",
        AsyncMock(side_effect=remove_file),
    )
    return folder_dir


# ---------- POST /api/roms/{id}/soundtracks ----------


def test_upload_soundtrack_success(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )

    assert response.status_code == status.HTTP_200_OK
    written = soundtrack_fs / "track1.mp3"
    assert written.exists()
    assert written.read_bytes() == MP3_BYTES

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    soundtracks = [
        f for f in rom_after.files if f.category == RomFileCategory.SOUNDTRACK
    ]
    assert len(soundtracks) == 1
    assert soundtracks[0].file_name == "track1.mp3"
    assert soundtracks[0].file_path == f"{multi_file_rom.full_path}/soundtrack"
    assert soundtracks[0].file_size_bytes == len(MP3_BYTES)


def test_upload_soundtrack_upserts_on_reupload(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    for _ in range(2):
        response = client.post(
            f"/api/roms/{multi_file_rom.id}/soundtracks",
            headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
            files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
        )
        assert response.status_code == status.HTTP_200_OK

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    soundtracks = [
        f for f in rom_after.files if f.category == RomFileCategory.SOUNDTRACK
    ]
    assert len(soundtracks) == 1


def test_upload_soundtrack_rejects_single_file_rom(
    client: TestClient,
    access_token: str,
    rom: Rom,
    soundtrack_fs: Path,
):
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=rom.fs_name,
            file_path=rom.fs_path,
            file_size_bytes=1,
            category=RomFileCategory.GAME,
        )
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "folder-based" in response.json()["detail"]


def test_upload_soundtrack_rejects_invalid_extension(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "notes.txt"},
        files={"notes.txt": ("notes.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported audio file type" in response.json()["detail"]


# ---------- DELETE /api/roms/{id}/soundtracks/{file_id} ----------


def test_delete_soundtrack_success(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    (soundtrack_fs / "track1.mp3").write_bytes(MP3_BYTES)
    track = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="track1.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=len(MP3_BYTES),
            category=RomFileCategory.SOUNDTRACK,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/soundtracks/{track.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(track.id) is None
    assert not (soundtrack_fs / "track1.mp3").exists()


def test_delete_soundtrack_wrong_rom_returns_404(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    rom: Rom,
    soundtrack_fs: Path,
):
    track = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="track1.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=len(MP3_BYTES),
            category=RomFileCategory.SOUNDTRACK,
        )
    )

    response = client.delete(
        f"/api/roms/{rom.id}/soundtracks/{track.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_soundtrack_wrong_category_returns_404(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    not_soundtrack = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="english.pdf",
            file_path=f"{multi_file_rom.full_path}/manual",
            file_size_bytes=10,
            category=RomFileCategory.MANUAL,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/soundtracks/{not_soundtrack.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- audio metadata extraction on upload ----------


def test_upload_soundtrack_extracts_audio_meta(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_meta = {
        "title": "The Theme",
        "artist": "Composer X",
        "album": "OST",
        "year": "1995",
        "genre": "Chiptune",
        "track": "01",
        "disc": "1",
        "duration_seconds": 123.4,
        "has_embedded_cover": True,
        "file_mtime": 1_700_000_000.0,
        "file_size": len(MP3_BYTES),
    }
    monkeypatch.setattr(
        soundtrack_endpoint, "extract_audio_meta", lambda _path: fake_meta
    )
    monkeypatch.setattr(
        soundtrack_endpoint,
        "persist_embedded_cover",
        lambda **_kwargs: f"roms/{_kwargs['platform_id']}/{_kwargs['rom_id']}"
        f"/soundtracks/{_kwargs['file_id']}.jpg",
    )

    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_200_OK

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    soundtracks = [
        f for f in rom_after.files if f.category == RomFileCategory.SOUNDTRACK
    ]
    assert len(soundtracks) == 1
    track = soundtracks[0]
    assert track.audio_meta is not None
    assert track.audio_meta["title"] == "The Theme"
    assert track.audio_meta["duration_seconds"] == 123.4
    assert track.audio_meta["has_embedded_cover"] is True
    assert (
        track.audio_meta["cover_path"]
        == f"roms/{multi_file_rom.platform_id}/{multi_file_rom.id}"
        f"/soundtracks/{track.id}.jpg"
    )


def test_upload_soundtrack_no_cover_leaves_cover_path_unset(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        soundtrack_endpoint,
        "extract_audio_meta",
        lambda _path: {"has_embedded_cover": False},
    )
    cover_calls: list[dict] = []

    def _record_cover_call(**kw: object) -> None:
        cover_calls.append(kw)

    monkeypatch.setattr(
        soundtrack_endpoint, "persist_embedded_cover", _record_cover_call
    )

    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "track1.mp3"},
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_200_OK
    assert cover_calls == []  # never called when has_embedded_cover is False

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    track = next(f for f in rom_after.files if f.category == RomFileCategory.SOUNDTRACK)
    assert track.audio_meta.get("cover_path") is None


# ---------- GET /api/roms/{id}/soundtracks/metadata ----------


def test_get_soundtrack_metadata_returns_tracks_sorted(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    meta_b = {
        "title": "B side",
        "artist": "A",
        "album": None,
        "year": None,
        "genre": None,
        "track": None,
        "disc": None,
        "duration_seconds": 42.0,
        "has_embedded_cover": False,
    }
    meta_a = {**meta_b, "title": "A side", "has_embedded_cover": True}
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="b_track.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=10,
            category=RomFileCategory.SOUNDTRACK,
            audio_meta=meta_b,
        )
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="a_track.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=10,
            category=RomFileCategory.SOUNDTRACK,
            audio_meta=meta_a,
        )
    )

    response = client.get(
        f"/api/roms/{multi_file_rom.id}/soundtracks/metadata",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [t["file_name"] for t in body] == ["a_track.mp3", "b_track.mp3"]
    assert body[0]["audio_meta"]["title"] == "A side"
    assert body[0]["audio_meta"]["has_embedded_cover"] is True
    assert body[1]["audio_meta"]["duration_seconds"] == 42.0


def test_get_soundtrack_metadata_empty_for_rom_without_tracks(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
):
    response = client.get(
        f"/api/roms/{multi_file_rom.id}/soundtracks/metadata",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# ---------- cover cleanup on delete ----------


# ---------- permissions ----------


def test_upload_soundtrack_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={
            **_auth(viewer_access_token),
            "x-upload-filename": "track1.mp3",
        },
        files={"track1.mp3": ("track1.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_soundtrack_forbidden_viewer(
    client: TestClient,
    viewer_access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    track = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="track1.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=10,
            category=RomFileCategory.SOUNDTRACK,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/soundtracks/{track.id}",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------- path traversal ----------


def test_upload_soundtrack_rejects_traversal_filename(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    """x-upload-filename containing path components must be rejected with 400,
    exercising the real sanitizer — not the mocked validate_path."""
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={
            **_auth(access_token),
            "x-upload-filename": "../../evil.mp3",
        },
        files={"../../evil.mp3": ("evil.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "plain file name" in response.json()["detail"]
    # Nothing must escape the library sandbox.
    assert not (soundtrack_fs.parent / "evil.mp3").exists()
    assert not (soundtrack_fs / "evil.mp3").exists()


def test_upload_soundtrack_rejects_slash_filename(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={
            **_auth(access_token),
            "x-upload-filename": "sub/track.mp3",
        },
        files={"sub/track.mp3": ("track.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_upload_soundtrack_rejects_dotdot_only_filename(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": ".."},
        files={"..": ("..", MP3_BYTES, "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "filename" in response.json()["detail"].lower()


# ---------- 404 metadata ----------


def test_get_soundtrack_metadata_unknown_rom_returns_404(
    client: TestClient,
    access_token: str,
):
    response = client.get(
        "/api/roms/999999/soundtracks/metadata",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- malformed audio: real extract_audio_meta ----------


def test_upload_soundtrack_with_malformed_audio_still_succeeds(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    """The real extract_audio_meta must never raise — garbage bytes produce
    audio_meta=None, not a 500."""
    response = client.post(
        f"/api/roms/{multi_file_rom.id}/soundtracks",
        headers={**_auth(access_token), "x-upload-filename": "bad.mp3"},
        files={"bad.mp3": ("bad.mp3", b"\x00\x01\x02 not audio", "audio/mpeg")},
    )
    assert response.status_code == status.HTTP_200_OK

    rom_after = db_rom_handler.get_rom(multi_file_rom.id)
    soundtracks = [
        f for f in rom_after.files if f.category == RomFileCategory.SOUNDTRACK
    ]
    assert len(soundtracks) == 1
    # audio_meta is either None or a dict — garbage in must not raise.
    meta = soundtracks[0].audio_meta
    assert meta is None or isinstance(meta, dict)


# ---------- missing-file delete ----------


def test_delete_soundtrack_tolerates_missing_disk_file(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
):
    """DB row should still be dropped if the on-disk file is already gone."""
    track = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="missing.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=10,
            category=RomFileCategory.SOUNDTRACK,
        )
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/soundtracks/{track.id}",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert db_rom_handler.get_rom_file_by_id(track.id) is None


def test_delete_soundtrack_removes_persisted_cover(
    client: TestClient,
    access_token: str,
    multi_file_rom: Rom,
    soundtrack_fs: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (soundtrack_fs / "track1.mp3").write_bytes(MP3_BYTES)
    track = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=multi_file_rom.id,
            file_name="track1.mp3",
            file_path=f"{multi_file_rom.full_path}/soundtrack",
            file_size_bytes=len(MP3_BYTES),
            category=RomFileCategory.SOUNDTRACK,
            audio_meta={
                "has_embedded_cover": True,
                "cover_path": (
                    f"roms/{multi_file_rom.platform_id}/{multi_file_rom.id}"
                    "/soundtracks/9999.jpg"
                ),
            },
        )
    )
    removed: list[str] = []
    monkeypatch.setattr(
        soundtrack_endpoint,
        "remove_persisted_cover",
        lambda p: removed.append(p),
    )

    response = client.delete(
        f"/api/roms/{multi_file_rom.id}/soundtracks/{track.id}",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert removed == [
        f"roms/{multi_file_rom.platform_id}/{multi_file_rom.id}" "/soundtracks/9999.jpg"
    ]
    assert db_rom_handler.get_rom_file_by_id(track.id) is None
