import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from utils import get_version


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


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
    assert isinstance(frontend["UPLOAD_TIMEOUT"], int)
    assert isinstance(frontend["DISABLE_USERPASS_LOGIN"], bool)

    assert "OIDC" in heartbeat
    oidc = heartbeat["OIDC"]
    assert isinstance(oidc["ENABLED"], bool)
    assert isinstance(oidc["PROVIDER"], str)


def test_heartbeat_metadata(client):
    response = client.get("/api/heartbeat/metadata/launchbox")
    assert response.status_code == status.HTTP_200_OK

    heartbeat = response.json()
    assert heartbeat


def test_heartbeat_metadata_unknown_source(client):
    response = client.get("/api/heartbeat/metadata/unknown")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
