import io
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from anyio import Path as AnyioPath
from fastapi import status
from fastapi.testclient import TestClient
from tests.rom_patcher_stubs import APPEND_PATCH, install_fake_node

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from endpoints.roms import patch as patch_endpoint
from handler.auth.base_handler import oauth_handler
from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_rom_handler
from models.permission import HiddenEntity, PermEntity
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from utils.nginx import content_disposition
from utils.rom_patcher import PatcherInputError
from utils.zip_cache import ensure_zipfile_writable


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
        await AnyioPath(output_path).write_bytes(b"patched zip")
        return False

    monkeypatch.setattr(fs_rom_handler, "validate_path", lambda path: Path(path))
    monkeypatch.setattr(patch_endpoint, "apply_patch", patch)

    response = client.post(
        f"/api/roms/{rom_file.id}/patch",
        headers=_auth(access_token),
        data={
            "patch_file_id": str(patch_file.id),
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

    monkeypatch.setattr(fs_rom_handler, "validate_path", lambda path: Path(path))
    monkeypatch.setattr(patch_endpoint, "apply_patch", reject_patch)

    response = client.post(
        f"/api/roms/{rom_file.id}/patch",
        headers=_auth(access_token),
        data={"patch_file_id": str(patch_file.id)},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": "Select which file inside the ROM archive to patch"
    }


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "library"
    root.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", root)
    return root


class Scratch:
    """The temp dirs the endpoint makes, so the tests can see them go."""

    def __init__(self) -> None:
        self.made: list[Path] = []

    def all_removed(self) -> bool:
        return not any(path.exists() for path in self.made)


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Scratch:
    root = tmp_path / "scratch"
    root.mkdir()
    made = Scratch()
    mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(prefix: str | None = None) -> str:
        path = mkdtemp(prefix=prefix, dir=root)
        made.made.append(Path(path))
        return path

    monkeypatch.setattr(tempfile, "mkdtemp", recording_mkdtemp)
    return made


@pytest.fixture
def node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_node(tmp_path, monkeypatch, APPEND_PATCH)


def _file(
    library: Path,
    rom: Rom,
    name: str,
    content: bytes,
    category: RomFileCategory | None = None,
    **overrides: Any,
) -> RomFile:
    path = library / rom.fs_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=name,
            file_path=rom.fs_path,
            file_size_bytes=len(content),
            category=category,
            **overrides,
        )
    )


def _hide(rom: Rom, user: User) -> None:
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(entity=PermEntity.ROMS, entity_id=rom.id, user_id=user.id)
        )


def _user_auth(user: User) -> dict[str, str]:
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return _auth(token)


class TestPatchingALibraryFile:
    def test_returns_the_patched_rom(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        node: None,
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(library, rom, "translation.bps", b"+patch", RomFileCategory.PATCH)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            data={"patch_file_id": str(patch.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"rom+patch"
        assert response.headers["x-patch-validated"] == "true"
        assert response.headers["content-disposition"] == content_disposition(
            "game (patched-translation).sfc"
        )
        assert len(scratch.made) == 1
        assert scratch.all_removed()

    def test_names_the_output_as_asked_keeping_the_roms_extension(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        node: None,
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(library, rom, "translation.bps", b"+patch", RomFileCategory.PATCH)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            data={"patch_file_id": str(patch.id), "output_file_name": "My Hack.bin"},
        )

        assert response.headers["content-disposition"] == content_disposition(
            "My Hack.sfc"
        )

    def test_patches_a_member_of_a_zipped_rom(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        node: None,
    ):
        archive = io.BytesIO()
        ensure_zipfile_writable()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("game.sfc", b"rom")
            zipped.writestr("readme.txt", b"hi")
        game = _file(library, rom, "game.zip", archive.getvalue())
        patch = _file(library, rom, "translation.bps", b"+patch", RomFileCategory.PATCH)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            data={"patch_file_id": str(patch.id), "archive_member_name": "game.sfc"},
        )

        assert response.status_code == status.HTTP_200_OK
        with zipfile.ZipFile(io.BytesIO(response.content)) as zipped:
            assert zipped.read("game.sfc") == b"rom+patch"
            assert zipped.read("readme.txt") == b"hi"


class TestPatchingWithAnUpload:
    def test_returns_the_patched_rom(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        node: None,
    ):
        game = _file(library, rom, "game.sfc", b"rom")

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"rom+upload"
        assert response.headers["content-disposition"] == content_disposition(
            "game (patched-fix).sfc"
        )
        assert len(scratch.made) == 1
        assert scratch.all_removed()

    @pytest.mark.parametrize(
        ("name", "content", "detail"),
        [
            ("fix.txt", b"+upload", "Unsupported patch format '.txt'"),
            ("fix", b"+upload", "Unsupported patch format ''"),
            ("fix.ips", b"", "Uploaded patch file is empty"),
            ("fix.ips", b"x" * 65, "Patch file is too large to patch (max 64 bytes)"),
        ],
        ids=["unsupported", "no_extension", "empty", "too_large"],
    )
    def test_a_bad_upload_is_rejected(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        node: None,
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        content: bytes,
        detail: str,
    ):
        monkeypatch.setattr(patch_endpoint, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 64)
        game = _file(library, rom, "game.sfc", b"rom")

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": (name, content)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"].startswith(detail)
        assert len(scratch.made) == 1
        assert scratch.all_removed()


class TestRejections:
    @pytest.mark.parametrize("both", [False, True], ids=["neither", "both"])
    def test_needs_exactly_one_patch_source(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        both: bool,
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(library, rom, "translation.bps", b"+patch", RomFileCategory.PATCH)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            data={"patch_file_id": str(patch.id)} if both else {},
            files={"patch_file": ("fix.ips", b"+upload")} if both else None,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == (
            "Provide exactly one of a library patch file or an uploaded patch file"
        )

    def test_an_unknown_rom_file_is_not_found(
        self, client: TestClient, access_token: str
    ):
        response = client.post(
            "/api/roms/999999/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "ROM file with id 999999 not found"

    def test_a_rom_hidden_from_the_caller_is_not_found(
        self, client: TestClient, viewer_user: User, rom: Rom, library: Path
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        _hide(rom, viewer_user)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_user_auth(viewer_user),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"ROM file with id {game.id} not found"

    def test_a_rom_missing_from_disk_is_not_found(
        self, client: TestClient, access_token: str, rom: Rom, library: Path
    ):
        game = _file(library, rom, "game.sfc", b"rom", missing_from_fs=True)

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == (
            "ROM file 'game.sfc' is missing from filesystem"
        )

    def test_a_rom_over_the_size_limit_is_rejected(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(patch_endpoint, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 2)
        game = _file(library, rom, "game.sfc", b"rom")

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"].startswith("ROM file is too large to patch")

    def test_needs_the_roms_read_scope(
        self, client: TestClient, admin_user: User, rom: Rom, library: Path
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        token = oauth_handler.create_access_token(
            data={"sub": admin_user.username, "iss": "romm:oauth", "scopes": ""},
            expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
        )

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestLibraryPatchRejections:
    def _post(
        self, client: TestClient, headers: dict[str, str], game: RomFile, patch_id: int
    ) -> httpx2.Response:
        return client.post(
            f"/api/roms/{game.id}/patch",
            headers=headers,
            data={"patch_file_id": str(patch_id)},
        )

    def test_an_unknown_patch_is_not_found(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
    ):
        game = _file(library, rom, "game.sfc", b"rom")

        response = self._post(client, _auth(access_token), game, 999_999)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Patch file with id 999999 not found"
        assert len(scratch.made) == 1
        assert scratch.all_removed()

    def test_a_patch_on_a_hidden_rom_is_not_found(
        self,
        client: TestClient,
        viewer_user: User,
        rom: Rom,
        second_rom: Rom,
        library: Path,
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(
            library, second_rom, "translation.bps", b"+patch", RomFileCategory.PATCH
        )
        _hide(second_rom, viewer_user)

        response = self._post(client, _user_auth(viewer_user), game, patch.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"Patch file with id {patch.id} not found"

    def test_a_patch_missing_from_disk_is_not_found(
        self, client: TestClient, access_token: str, rom: Rom, library: Path
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(
            library,
            rom,
            "translation.bps",
            b"+patch",
            RomFileCategory.PATCH,
            missing_from_fs=True,
        )

        response = self._post(client, _auth(access_token), game, patch.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == (
            "Patch file 'translation.bps' is missing from filesystem"
        )

    def test_a_file_that_is_not_a_patch_is_rejected(
        self, client: TestClient, access_token: str, rom: Rom, library: Path
    ):
        game = _file(library, rom, "game.sfc", b"rom")
        manual = _file(library, rom, "manual.pdf", b"%PDF")

        response = self._post(client, _auth(access_token), game, manual.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"].startswith("Unsupported patch format '.pdf'")

    def test_a_patch_over_the_size_limit_is_rejected(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(patch_endpoint, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 4)
        game = _file(library, rom, "game.sfc", b"rom")
        patch = _file(library, rom, "translation.bps", b"+patch", RomFileCategory.PATCH)

        response = self._post(client, _auth(access_token), game, patch.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"].startswith("Patch file is too large to patch")


class TestPatcherFailures:
    def test_a_patcher_error_is_a_500_without_its_details(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        install_fake_node(
            tmp_path,
            monkeypatch,
            """
            sys.stderr.write(json.dumps({"error": "ROM file not found: /srv/secret"}))
            sys.exit(2)
            """,
        )
        game = _file(library, rom, "game.sfc", b"rom")

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Patching failed"}
        assert len(scratch.made) == 1
        assert scratch.all_removed()

    def test_an_unexpected_error_is_a_500(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        library: Path,
        scratch: Scratch,
        monkeypatch: pytest.MonkeyPatch,
    ):
        async def explode(*_args: Any) -> bool:
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(patch_endpoint, "apply_patch", explode)
        game = _file(library, rom, "game.sfc", b"rom")

        response = client.post(
            f"/api/roms/{game.id}/patch",
            headers=_auth(access_token),
            files={"patch_file": ("fix.ips", b"+upload")},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Patching failed"}
        assert len(scratch.made) == 1
        assert scratch.all_removed()
