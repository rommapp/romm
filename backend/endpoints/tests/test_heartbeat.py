from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_heartbeat():
    response = client.get("/heartbeat")
    assert response.status_code == 200
    assert response.json() == {
        'ROMM_AUTH_ENABLED': True,
        'ENABLE_RESCAN_ON_FILESYSTEM_CHANGE': True,
        'ENABLE_SCHEDULED_RESCAN': True,
        'ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB': True,
        'ENABLE_SCHEDULED_UPDATE_MAME_XML': True,
        'RESCAN_ON_FILESYSTEM_CHANGE_DELAY': 5,
        'SCHEDULED_RESCAN_CRON': '0 3 * * *',
        'SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON': '0 4 * * *',
        'SCHEDULED_UPDATE_MAME_XML_CRON': '0 5 * * *',
        'RUNR_ACTIVE_PLATFORMS': None,
        'RUNR_ENABLED': False,
        'RUNR_URL': None,
    }
