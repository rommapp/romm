from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_heartbeat():
    response = client.get("/heartbeat")
    assert response.status_code == 200
    assert response.json() == {
        "ROMM_AUTH_ENABLED": True,
        "WATCHER": {
            "ENABLED": True,
            "TITLE": "Rescan on filesystem change",
            "MESSAGE": "Runs a scan when a change is detected in the library path, with a 5 minute delay",
        },
        "SCHEDULER": {
            "RESCAN": {
                "ENABLED": True,
                "CRON": "0 3 * * *",
                "TITLE": "Scheduled rescan",
                "MESSAGE": "Rescans the entire library",
            },
            "SWITCH_TITLEDB": {
                "ENABLED": True,
                "CRON": "0 4 * * *",
                "TITLE": "Scheduled Switch TitleDB update",
                "MESSAGE": "Updates the Nintedo Switch TitleDB file",
            },
            "MAME_XML": {
                "ENABLED": True,
                "CRON": "0 5 * * *",
                "TITLE": "Scheduled MAME XML update",
                "MESSAGE": "Updates the MAME XML file",
            },
        },
    }
