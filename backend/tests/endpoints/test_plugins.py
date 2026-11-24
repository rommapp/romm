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
                        "platforms": ["ngc", "wii"],
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
    action = plugins[0]["actions"][0]
    assert action["url"] == "rommdeck://open?rom={rom_id}&platform={platform_slug}"
    assert action["platforms"] == ["ngc", "wii"]
    assert action["image"] is None

def test_get_plugin_facts_fills_a_panel_from_its_source(
    client, access_token, tmp_path, monkeypatch
):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path))
    folder = tmp_path / "emuready"
    folder.mkdir()
    (folder / plugin_handler.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "id": "emuready",
                "name": "EmuReady",
                "settings": [
                    {
                        "key": "base_url",
                        "label": "Address",
                        "type": "url",
                        "default": "https://example.com",
                    }
                ],
                "actions": [
                    {
                        "id": "open",
                        "label": "Open",
                        "url": "{setting.base_url}/listings",
                    }
                ],
                "facts": [
                    {
                        "id": "handheld",
                        "label": "Handheld reports",
                        "action": "open",
                        "url": "{setting.base_url}/api/listings",
                        "query": {"input": '{"json":{"search":"{rom_name}"}}'},
                        "list_path": "listings",
                        "group_by": "emulator",
                        "rating_field": "rating",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from endpoints import plugins as plugin_endpoints
    from handler import plugin_facts

    monkeypatch.setattr(
        plugin_endpoints,
        "_rom_values",
        lambda request, rom_id: {
            "rom_id": str(rom_id),
            "rom_name": "Luigi's Mansion",
            "platform_slug": "ngc",
            "platform_name": "Nintendo GameCube",
            "file_name": "Luigi's Mansion (USA).iso",
        },
    )
    monkeypatch.setattr(
        plugin_facts,
        "_fetch",
        lambda url: {
            "listings": [
                {"emulator": "Dolphin", "rating": "Perfect"},
                {"emulator": "Dolphin", "rating": "Great"},
            ]
        },
    )
    monkeypatch.setattr(plugin_facts, "refused_source", lambda url: None)
    plugin_facts.forget_all()

    response = client.get(
        "/api/plugins/emuready/facts?rom_id=1",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    fact = response.json()["facts"][0]
    assert fact["label"] == "Handheld reports"
    assert fact["total"] == 2
    assert fact["groups"][0]["key"] == "Dolphin"
    assert fact["groups"][0]["counts"] == {"Perfect": 1, "Great": 1}


def test_the_plugin_list_says_a_panel_exists_without_its_source(
    client, access_token, tmp_path, monkeypatch
):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path))
    folder = tmp_path / "emuready"
    folder.mkdir()
    (folder / plugin_handler.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "id": "emuready",
                "name": "EmuReady",
                "actions": [{"id": "open", "label": "Open", "url": "https://example.com"}],
                "facts": [
                    {
                        "id": "handheld",
                        "label": "Handheld reports",
                        "action": "open",
                        "url": "https://example.com/secret-path",
                        "list_path": "listings",
                        "group_by": "emulator",
                        "rating_field": "rating",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(
        "/api/plugins", headers={"Authorization": f"Bearer {access_token}"}
    )

    plugin = response.json()[0]
    assert plugin["facts"] == [
        {
            "id": "handheld",
            "label": "Handheld reports",
            "slot": "game.details",
            "action": "open",
        }
    ]
    assert "secret-path" not in response.text

