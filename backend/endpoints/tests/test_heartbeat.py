from fastapi.testclient import TestClient

from main import app

def test_heartbeat():
    with TestClient(app) as client:
        response = client.get("/heartbeat")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
