from fastapi.testclient import TestClient

from main import app


def test_platforms(access_token, platform):
    with TestClient(app) as client:
        response = client.get("/platforms")
        assert response.status_code == 403

        response = client.get(
            "/platforms", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        
        platforms = response.json()
        assert len(platforms) == 1
