"""Author identity on the note responses, which no note row stores itself."""

from fastapi import status
from fastapi.testclient import TestClient

from models.rom import Rom
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_note_responses_carry_author_identity(
    client: TestClient, access_token: str, rom: Rom, admin_user: User
):
    created = client.post(
        f"/api/roms/{rom.id}/notes",
        headers=_auth(access_token),
        json={
            "title": "Route order",
            "content": "Third phase first",
            "is_public": True,
        },
    )
    assert created.status_code == status.HTTP_200_OK

    listed = client.get(f"/api/roms/{rom.id}/notes", headers=_auth(access_token))
    assert listed.status_code == status.HTTP_200_OK

    notes = listed.json()
    assert [n["id"] for n in notes] == [created.json()["id"]]
    assert notes[0]["username"] == admin_user.username
    assert notes[0]["user_avatar_path"] == admin_user.avatar_path
    assert notes[0]["user_updated_at"] is not None

    detailed = client.get(f"/api/roms/{rom.id}", headers=_auth(access_token))
    assert detailed.status_code == status.HTTP_200_OK
    all_user_notes = detailed.json()["all_user_notes"]
    assert [n["id"] for n in all_user_notes] == [created.json()["id"]]
    assert all_user_notes[0]["username"] == admin_user.username
