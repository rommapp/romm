import json

from fastapi import status
from handler import plugin_handler


def test_get_plugins_requires_a_session(client):
    response = client.get("/api/plugins")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_plugins_is_empty_without_a_shelf(
    client, access_token, tmp_path, monkeypatch
):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path / "missing"))

    response = client.get(
        "/api/plugins", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_get_plugins_returns_the_manifest(client, access_token, tmp_path, monkeypatch):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path))
    folder = tmp_path / "rommdeck"
    folder.mkdir()
    (folder / plugin_handler.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "id": "rommdeck",
                "name": "RommDeck",
                "version": "1.0.0",
                "description": "Play on the device RommDeck manages.",
                "homepage": "https://github.com/s0liton/RommDeck",
                "actions": [
                    {
                        "id": "open",
                        "label": "Open in RommDeck",
                        "icon": "mdi-monitor",
                        "url": "rommdeck://open?rom={rom_id}&platform={platform_slug}",
                        "open": "new-tab",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(
        "/api/plugins", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    plugins = response.json()
    assert len(plugins) == 1
    assert plugins[0]["id"] == "rommdeck"
    assert plugins[0]["actions"][0]["url"] == (
        "rommdeck://open?rom={rom_id}&platform={platform_slug}"
    )
