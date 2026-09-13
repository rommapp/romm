from pathlib import Path

import pytest
from endpoints.roms import patch as patch_endpoint
from fastapi import status
from fastapi.testclient import TestClient
from handler.database import db_rom_handler
from models.rom import Rom, RomFile, RomFileCategory
from utils.rom_patcher import PatcherInputError


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _patch_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="translation.bps",
            file_path=rom.fs_path,
            file_size_bytes=100,
            category=RomFileCategory.PATCH,
        )
    )


def test_patch_rom_passes_archive_member_and_validation_header(
    client: TestClient,
    access_token: str,
    rom: Rom,
    rom_file: RomFile,
    monkeypatch: pytest.MonkeyPatch,
):
    patch_file = _patch_file(rom)
    received_member: str | None = None

    async def patch(
        _rom_path: Path,
        _patch_path: Path,
        output_path: Path,
        archive_member_name: str | None,
    ) -> bool:
        nonlocal received_member
        received_member = archive_member_name
        output_path.write_bytes(b"patched zip")
        return False

    monkeypatch.setattr(
        patch_endpoint.fs_rom_handler, "validate_path", lambda path: Path(path)
    )
    monkeypatch.setattr(patch_endpoint, "apply_patch", patch)

    response = client.post(
        f"/api/roms/{rom_file.id}/patch",
        headers=_auth(access_token),
        data={
            "patch_file_id": patch_file.id,
            "archive_member_name": "roms/game.sfc",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"patched zip"
    assert response.headers["x-patch-validated"] == "false"
    assert received_member == "roms/game.sfc"


def test_patch_rom_returns_bad_request_for_invalid_archive(
    client: TestClient,
    access_token: str,
    rom: Rom,
    rom_file: RomFile,
    monkeypatch: pytest.MonkeyPatch,
):
    patch_file = _patch_file(rom)

    async def reject_patch(*_args, **_kwargs) -> bool:
        raise PatcherInputError("Select which file inside the ROM archive to patch")

    monkeypatch.setattr(
        patch_endpoint.fs_rom_handler, "validate_path", lambda path: Path(path)
    )
    monkeypatch.setattr(patch_endpoint, "apply_patch", reject_patch)

    response = client.post(
        f"/api/roms/{rom_file.id}/patch",
        headers=_auth(access_token),
        data={"patch_file_id": patch_file.id},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": "Select which file inside the ROM archive to patch"
    }
