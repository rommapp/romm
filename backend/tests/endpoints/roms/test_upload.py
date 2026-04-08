from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import upload as upload_endpoint
from models.platform import Platform


@pytest.fixture
def upload_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    uploads_tmp = tmp_path / "uploads"
    final_dir = tmp_path / "library"

    async def make_directory(_path: str) -> None:
        final_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(upload_endpoint, "ROM_UPLOAD_TMP_BASE", uploads_tmp)
    monkeypatch.setattr(
        upload_endpoint.fs_rom_handler, "get_roms_fs_structure", lambda _slug: "roms"
    )
    monkeypatch.setattr(
        upload_endpoint.fs_rom_handler,
        "validate_path",
        lambda path: final_dir / Path(path).name,
    )
    monkeypatch.setattr(
        upload_endpoint.fs_rom_handler, "file_exists", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        upload_endpoint.fs_rom_handler,
        "make_directory",
        AsyncMock(side_effect=make_directory),
    )

    return {"uploads_tmp": uploads_tmp, "final_dir": final_dir}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _start_upload(
    client: TestClient,
    token: str,
    platform_id: int,
    *,
    filename: str = "game.zip",
    total_size: int = 11,
    total_chunks: int = 2,
):
    response = client.post(
        "/api/roms/upload/start",
        headers={
            **_auth_headers(token),
            "x-upload-platform": str(platform_id),
            "x-upload-filename": filename,
            "x-upload-total-size": str(total_size),
            "x-upload-total-chunks": str(total_chunks),
        },
    )
    return response


def test_start_chunked_upload_success(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    response = _start_upload(client, access_token, platform.id)

    assert response.status_code == status.HTTP_201_CREATED
    upload_id = response.json()["upload_id"]
    assert UUID(upload_id)


def test_start_chunked_upload_platform_not_found(
    client: TestClient,
    access_token: str,
    upload_fs: dict,
):
    response = _start_upload(client, access_token, platform_id=999999)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Platform not found"


def test_upload_chunk_complete_success(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    start_response = _start_upload(
        client,
        access_token,
        platform.id,
        filename="metroid.zip",
        total_size=11,
        total_chunks=2,
    )
    upload_id = start_response.json()["upload_id"]

    first = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    second = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "1"},
        content=b"GHIJK",
    )
    complete = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert complete.status_code == status.HTTP_201_CREATED

    final_file = upload_fs["final_dir"] / "metroid.zip"
    assert final_file.exists()
    assert final_file.read_bytes() == b"ABCDEFGHIJK"


def test_upload_chunk_invalid_upload_id(client: TestClient, access_token: str):
    response = client.put(
        "/api/roms/upload/not-a-uuid",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"chunk",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid upload ID"


def test_upload_chunk_forbidden_user(
    client: TestClient,
    access_token: str,
    editor_access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(editor_access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Forbidden"


def test_upload_chunk_oversized_returns_413(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(upload_endpoint, "ROM_UPLOAD_MAX_CHUNK_SIZE", 6)

    start_response = _start_upload(
        client,
        access_token,
        platform.id,
        total_size=12,
        total_chunks=2,
    )
    upload_id = start_response.json()["upload_id"]

    response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"1234567",
    )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"] == "Chunk exceeds maximum allowed size"


def test_complete_missing_chunks_returns_400(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    upload_response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    complete_response = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert upload_response.status_code == status.HTTP_200_OK
    assert complete_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Missing chunks" in complete_response.json()["detail"]


def test_complete_invalid_upload_id(client: TestClient, access_token: str):
    response = client.post(
        "/api/roms/upload/not-a-uuid/complete",
        headers=_auth_headers(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid upload ID"


def test_cancel_upload_cleans_temp_files(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    upload_response = client.put(
        f"/api/roms/upload/{upload_id}",
        headers={**_auth_headers(access_token), "x-chunk-index": "0"},
        content=b"ABCDEF",
    )
    chunk_path = upload_fs["uploads_tmp"] / upload_id / "00000"
    assert chunk_path.exists()

    cancel_response = client.post(
        f"/api/roms/upload/{upload_id}/cancel",
        headers=_auth_headers(access_token),
    )

    assert upload_response.status_code == status.HTTP_200_OK
    assert cancel_response.status_code == status.HTTP_204_NO_CONTENT
    assert not chunk_path.exists()


def test_complete_after_cancel_returns_404(
    client: TestClient,
    access_token: str,
    platform: Platform,
    upload_fs: dict,
):
    start_response = _start_upload(client, access_token, platform.id)
    upload_id = start_response.json()["upload_id"]

    cancel_response = client.post(
        f"/api/roms/upload/{upload_id}/cancel",
        headers=_auth_headers(access_token),
    )
    complete_response = client.post(
        f"/api/roms/upload/{upload_id}/complete",
        headers=_auth_headers(access_token),
    )

    assert cancel_response.status_code == status.HTTP_204_NO_CONTENT
    assert complete_response.status_code == status.HTTP_404_NOT_FOUND
