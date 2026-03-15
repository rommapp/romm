from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from exceptions.fs_exceptions import PlatformAlreadyExistsException
from utils import get_version


def test_heartbeat(client):
    response = client.get("/api/heartbeat")
    assert response.status_code == status.HTTP_200_OK

    heartbeat = response.json()

    assert "SYSTEM" in heartbeat
    system = heartbeat["SYSTEM"]
    assert system["VERSION"] == get_version()
    assert isinstance(system["SHOW_SETUP_WIZARD"], bool)

    assert "METADATA_SOURCES" in heartbeat
    metadata = heartbeat["METADATA_SOURCES"]
    assert isinstance(metadata["ANY_SOURCE_ENABLED"], bool)
    assert isinstance(metadata["IGDB_API_ENABLED"], bool)
    assert isinstance(metadata["MOBY_API_ENABLED"], bool)
    assert isinstance(metadata["SS_API_ENABLED"], bool)
    assert isinstance(metadata["STEAMGRIDDB_API_ENABLED"], bool)
    assert isinstance(metadata["RA_API_ENABLED"], bool)
    assert isinstance(metadata["LAUNCHBOX_API_ENABLED"], bool)
    assert isinstance(metadata["PLAYMATCH_API_ENABLED"], bool)
    assert isinstance(metadata["HASHEOUS_API_ENABLED"], bool)
    assert isinstance(metadata["TGDB_API_ENABLED"], bool)
    assert isinstance(metadata["FLASHPOINT_API_ENABLED"], bool)

    assert "FILESYSTEM" in heartbeat
    filesystem = heartbeat["FILESYSTEM"]
    assert isinstance(filesystem["FS_PLATFORMS"], list)

    assert "EMULATION" in heartbeat
    emulation = heartbeat["EMULATION"]
    assert isinstance(emulation["DISABLE_EMULATOR_JS"], bool)
    assert isinstance(emulation["DISABLE_RUFFLE_RS"], bool)

    assert "FRONTEND" in heartbeat
    frontend = heartbeat["FRONTEND"]
    assert isinstance(frontend["DISABLE_USERPASS_LOGIN"], bool)

    assert "OIDC" in heartbeat
    oidc = heartbeat["OIDC"]
    assert isinstance(oidc["ENABLED"], bool)
    assert isinstance(oidc["PROVIDER"], str)
    assert isinstance(oidc["RP_INITIATED_LOGOUT"], bool)


def test_heartbeat_metadata(client):
    response = client.get("/api/heartbeat/metadata/launchbox")
    assert response.status_code == status.HTTP_200_OK

    heartbeat = response.json()
    assert heartbeat


def test_heartbeat_metadata_unknown_source(client):
    response = client.get("/api/heartbeat/metadata/unknown")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_get_setup_library_info_structure_a_detected(client, access_token):
    """Test get_setup_library_info with Structure A detected"""
    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "struct_a"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.get_platforms"
        ) as mock_get_platforms:
            mock_get_platforms.return_value = ["n64", "psx"]

            # Create mock entry objects with .name attribute
            def create_mock_entry(name):
                entry = MagicMock()
                entry.name = name
                return entry

            async def mock_iterdir_n64():
                yield create_mock_entry("game1.z64")
                yield create_mock_entry("game2.z64")

            async def mock_iterdir_psx():
                yield create_mock_entry("game1.iso")

            with patch("endpoints.heartbeat.AnyioPath") as mock_anyio_path:
                # Create side effects for multiple calls to AnyioPath()
                path_instances = []

                # First call - n64 roms directory
                mock_n64_path = AsyncMock()
                mock_n64_path.exists = AsyncMock(return_value=True)
                mock_n64_path.iterdir = mock_iterdir_n64
                path_instances.append(mock_n64_path)

                # Second call - psx roms directory
                mock_psx_path = AsyncMock()
                mock_psx_path.exists = AsyncMock(return_value=True)
                mock_psx_path.iterdir = mock_iterdir_psx
                path_instances.append(mock_psx_path)

                mock_anyio_path.side_effect = path_instances

                response = client.get(
                    "/api/setup/library",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()

                assert data["detected_structure"] == "struct_a"
                assert len(data["existing_platforms"]) == 2
                assert data["existing_platforms"][0]["fs_slug"] == "n64"
                assert data["existing_platforms"][0]["rom_count"] == 2
                assert data["existing_platforms"][1]["fs_slug"] == "psx"
                assert data["existing_platforms"][1]["rom_count"] == 1
                assert "supported_platforms" in data


def test_get_setup_library_info_structure_b_detected(client, admin_user, access_token):
    """Test get_setup_library_info with Structure B detected"""
    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "B"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.get_platforms"
        ) as mock_get_platforms:
            mock_get_platforms.return_value = ["gba"]

            # Create mock entry objects with .name attribute
            def create_mock_entry(name):
                entry = MagicMock()
                entry.name = name
                return entry

            async def mock_iterdir_gba():
                yield create_mock_entry("game1.gba")
                yield create_mock_entry("game2.gba")
                yield create_mock_entry("game3.gba")

            with patch("endpoints.heartbeat.AnyioPath") as mock_anyio_path:
                # Create mock for gba roms directory
                mock_gba_path = AsyncMock()
                mock_gba_path.exists = AsyncMock(return_value=True)
                mock_gba_path.iterdir = mock_iterdir_gba

                mock_anyio_path.return_value = mock_gba_path

                response = client.get(
                    "/api/setup/library",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()

                assert data["detected_structure"] == "B"
                assert len(data["existing_platforms"]) == 1
                assert data["existing_platforms"][0]["fs_slug"] == "gba"
                assert data["existing_platforms"][0]["rom_count"] == 3


def test_get_setup_library_info_no_structure_detected(client, admin_user, access_token):
    """Test get_setup_library_info when no structure is detected"""
    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = None

        with patch(
            "endpoints.heartbeat.fs_platform_handler.get_platforms"
        ) as mock_get_platforms:
            mock_get_platforms.return_value = []

            response = client.get(
                "/api/setup/library",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["detected_structure"] is None
            assert data["existing_platforms"] == []
            assert "supported_platforms" in data


def test_get_setup_library_info_handles_errors(client, admin_user, access_token):
    """Test get_setup_library_info handles filesystem errors gracefully"""
    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "struct_a"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.get_platforms"
        ) as mock_get_platforms:
            # Simulate error retrieving platforms
            mock_get_platforms.side_effect = Exception("Filesystem error")

            response = client.get(
                "/api/setup/library",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should return empty platforms list on error
            assert data["existing_platforms"] == []


def test_create_setup_platforms_success(client, admin_user, access_token):
    """Test create_setup_platforms successfully creates platforms"""
    platform_slugs = ["n64", "psx", "gba"]

    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "struct_a"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.add_platform"
        ) as mock_add_platform:
            mock_add_platform.return_value = None  # Successful creation

            response = client.post(
                "/api/setup/platforms",
                json=platform_slugs,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            assert data["success"] is True
            assert data["created_count"] == 3
            assert "Successfully created 3 platform folder(s)" in data["message"]
            assert mock_add_platform.call_count == 3


def test_create_setup_platforms_empty_list(client, admin_user, access_token):
    """Test create_setup_platforms with empty platform list"""
    response = client.post(
        "/api/setup/platforms",
        json=[],
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert data["success"] is True
    assert data["created_count"] == 0
    assert data["message"] == "No platforms selected"


def test_create_setup_platforms_creates_structure_a_when_none_exists(
    client, admin_user, access_token
):
    """Test create_setup_platforms creates Structure A when no structure detected"""
    platform_slugs = ["n64"]

    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = None  # No structure detected

        with patch("os.makedirs") as mock_makedirs:
            with patch("endpoints.heartbeat.fs_platform_handler.add_platform"):
                response = client.post(
                    "/api/setup/platforms",
                    json=platform_slugs,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                assert response.status_code == status.HTTP_201_CREATED
                # Should create roms folder first
                mock_makedirs.assert_called_once()
                assert "roms" in str(mock_makedirs.call_args[0][0])


def test_create_setup_platforms_skips_existing_platforms(
    client, admin_user, access_token
):
    """Test create_setup_platforms skips platforms that already exist"""
    platform_slugs = ["n64", "psx", "gba"]

    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "struct_a"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.add_platform"
        ) as mock_add_platform:
            # First platform already exists, second succeeds, third succeeds
            mock_add_platform.side_effect = [
                PlatformAlreadyExistsException("n64"),
                None,
                None,
            ]

            response = client.post(
                "/api/setup/platforms",
                json=platform_slugs,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            assert data["success"] is True
            # Should only count 2 created (psx and gba)
            assert data["created_count"] == 2


def test_create_setup_platforms_handles_permission_errors(
    client, admin_user, access_token
):
    """Test create_setup_platforms handles permission errors"""
    platform_slugs = ["n64"]

    with patch(
        "endpoints.heartbeat.fs_platform_handler.detect_library_structure"
    ) as mock_detect:
        mock_detect.return_value = "struct_a"

        with patch(
            "endpoints.heartbeat.fs_platform_handler.add_platform"
        ) as mock_add_platform:
            mock_add_platform.side_effect = PermissionError("Permission denied")

            response = client.post(
                "/api/setup/platforms",
                json=platform_slugs,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create some platform folders" in response.json()["detail"]
