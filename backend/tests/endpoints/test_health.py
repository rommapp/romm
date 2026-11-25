from fastapi import status


def test_live_answers_ok_without_auth(client):
    response = client.get("/api/health/live")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
