import pytest
from fastapi.testclient import TestClient
from main import app
from utils import get_version


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_heartbeat(client):
    response = client.get("/api/heartbeat")
    assert response.status_code == 200

    heartbeat = response.json()
    assert heartbeat.get("SYSTEM").get("VERSION") == get_version()
    assert heartbeat.get("WATCHER").get("ENABLED")
    assert heartbeat.get("WATCHER").get("TITLE") == "Rescan on filesystem change"
    assert heartbeat.get("SCHEDULER").get("RESCAN").get("ENABLED")
    assert heartbeat.get("SCHEDULER").get("RESCAN").get("CRON") == "0 3 * * *"
    assert heartbeat.get("SCHEDULER").get("RESCAN").get("TITLE") == "Scheduled rescan"
    assert heartbeat.get("SCHEDULER").get("SWITCH_TITLEDB").get("ENABLED")
    assert heartbeat.get("SCHEDULER").get("SWITCH_TITLEDB").get("CRON") == "0 4 * * *"
    assert (
        heartbeat.get("SCHEDULER").get("SWITCH_TITLEDB").get("TITLE")
        == "Scheduled Switch TitleDB update"
    )
    assert heartbeat.get("FRONTEND").get("UPLOAD_TIMEOUT") == 20
