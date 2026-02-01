from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from handler.walkthrough_handler import (
    InvalidWalkthroughURLError,
    WalkthroughContentNotFound,
    WalkthroughFormat,
    WalkthroughSource,
)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_walkthrough_requires_auth(client):
    response = client.post(
        "/api/walkthroughs/fetch",
        json={
            "url": "https://gamefaqs.gamespot.com/snes/guide/faqs/1",
            "format": "html",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_walkthrough_success(client, access_token):
    fake_result = {
        "url": "https://gamefaqs.gamespot.com/snes/guide/faqs/1",
        "title": "Guide title",
        "author": "Guide author",
        "source": WalkthroughSource.GAMEFAQS,
        "format": WalkthroughFormat.HTML,
        "content": "<pre>content</pre>",
    }

    with patch(
        "endpoints.walkthrough.fetch_walkthrough",
        AsyncMock(return_value=fake_result),
    ):
        response = client.post(
            "/api/walkthroughs/fetch",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"url": fake_result["url"], "format": "html"},
        )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["title"] == fake_result["title"]
    assert payload["author"] == fake_result["author"]
    assert payload["source"] == WalkthroughSource.GAMEFAQS
    assert payload["format"] == WalkthroughFormat.HTML
    assert payload["content"] == fake_result["content"]


def test_walkthrough_invalid_url(client, access_token):
    with patch(
        "endpoints.walkthrough.fetch_walkthrough",
        AsyncMock(side_effect=InvalidWalkthroughURLError("bad url")),
    ):
        response = client.post(
            "/api/walkthroughs/fetch",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"url": "https://example.com", "format": "html"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_walkthrough_not_found(client, access_token):
    with patch(
        "endpoints.walkthrough.fetch_walkthrough",
        AsyncMock(side_effect=WalkthroughContentNotFound("missing content")),
    ):
        response = client.post(
            "/api/walkthroughs/fetch",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "url": "https://gamefaqs.gamespot.com/snes/563504-secret-of-mana/faqs/55474",
                "format": "text",
            },
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_walkthrough_for_rom(client, access_token, rom):
    fake_result = {
        "url": "https://gamefaqs.gamespot.com/snes/guide/faqs/1",
        "title": "Guide title",
        "author": "Guide author",
        "source": WalkthroughSource.GAMEFAQS,
        "format": WalkthroughFormat.HTML,
        "content": "<pre>content</pre>",
    }
    with patch(
        "endpoints.walkthrough.fetch_walkthrough",
        AsyncMock(return_value=fake_result),
    ):
        response = client.post(
            f"/api/walkthroughs/roms/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"url": fake_result["url"]},
        )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["rom_id"] == rom.id
    assert data["url"] == fake_result["url"]
    assert data["title"] == fake_result["title"]
    assert data["author"] == fake_result["author"]
    assert data["source"] == WalkthroughSource.GAMEFAQS

    # Fetch list
    list_response = client.get(
        f"/api/walkthroughs/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert list_response.status_code == status.HTTP_200_OK
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == data["id"]
    assert items[0]["title"] == fake_result["title"]
    assert items[0]["author"] == fake_result["author"]

    # Delete
    delete_response = client.delete(
        f"/api/walkthroughs/{data['id']}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == status.HTTP_200_OK
