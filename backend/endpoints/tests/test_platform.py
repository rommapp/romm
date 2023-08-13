from fastapi.testclient import TestClient

from main import app

def test_platforms():
    with TestClient(app) as client:
        response = client.get("/platforms")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
