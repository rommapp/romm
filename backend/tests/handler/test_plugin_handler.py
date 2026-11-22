import json
from pathlib import Path

import pytest
from handler import plugin_handler
from handler.plugin_handler import list_plugins


def write_plugin(base: Path, folder: str, manifest: dict | str) -> Path:
    path = base / folder
    path.mkdir(parents=True)
    text = manifest if isinstance(manifest, str) else json.dumps(manifest)
    (path / plugin_handler.MANIFEST_NAME).write_text(text, encoding="utf-8")
    return path


def manifest(plugin_id: str = "rommdeck", **overrides) -> dict:
    data = {
        "id": plugin_id,
        "name": "RommDeck",
        "version": "1.0.0",
        "actions": [
            {
                "id": "open",
                "label": "Open in RommDeck",
                "icon": "mdi-monitor",
                "url": "rommdeck://open?rom={rom_id}",
            }
        ],
    }
    data.update(overrides)
    return data


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path))
    return tmp_path


def test_no_shelf_is_an_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin_handler, "PLUGINS_BASE_PATH", str(tmp_path / "missing"))

    assert list_plugins() == []


def test_plugin_is_read_off_the_shelf(shelf):
    write_plugin(shelf, "rommdeck", manifest())

    plugins = list_plugins()

    assert [plugin.id for plugin in plugins] == ["rommdeck"]
    assert plugins[0].name == "RommDeck"
    assert plugins[0].actions[0].url == "rommdeck://open?rom={rom_id}"
    assert plugins[0].actions[0].open == "new-tab"


def test_plugins_are_sorted_by_name(shelf):
    write_plugin(shelf, "zulu", manifest("zulu", name="Zulu"))
    write_plugin(shelf, "alpha", manifest("alpha", name="alpha"))

    assert [plugin.id for plugin in list_plugins()] == ["alpha", "zulu"]


def test_a_broken_manifest_does_not_hide_the_shelf(shelf):
    write_plugin(shelf, "broken", "{ not json")
    write_plugin(shelf, "rommdeck", manifest())

    assert [plugin.id for plugin in list_plugins()] == ["rommdeck"]


def test_a_manifest_without_an_id_or_name_is_skipped(shelf):
    write_plugin(shelf, "nameless", manifest("nameless", name=""))
    write_plugin(shelf, "no-id", manifest(""))

    assert list_plugins() == []


def test_a_repeated_id_is_skipped(shelf):
    write_plugin(shelf, "first", manifest("rommdeck", name="First"))
    write_plugin(shelf, "second", manifest("rommdeck", name="Second"))

    plugins = list_plugins()

    assert [plugin.name for plugin in plugins] == ["First"]


def test_a_plugin_without_actions_is_skipped(shelf):
    write_plugin(shelf, "empty", manifest(actions=[]))

    assert list_plugins() == []


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "/no/scheme/here",
        "rommdeck://open?rom={rom_id} and a space",
    ],
)
def test_an_unusable_url_is_dropped(shelf, url):
    path = write_plugin(shelf, "rommdeck", manifest())
    data = manifest()
    data["actions"][0]["url"] = url
    path.write_text(json.dumps(data), encoding="utf-8")

    assert list_plugins() == []


def test_an_unknown_placeholder_is_dropped(shelf):
    data = manifest()
    data["actions"][0]["url"] = "rommdeck://open?secret={user_token}"
    write_plugin(shelf, "rommdeck", data)

    assert list_plugins() == []


def test_a_bad_action_leaves_the_good_ones(shelf):
    data = manifest()
    data["actions"].append({"id": "bad", "label": "Bad", "url": "javascript:1"})
    write_plugin(shelf, "rommdeck", data)

    plugins = list_plugins()

    assert [action.id for action in plugins[0].actions] == ["open"]


def test_a_manifest_too_large_to_read_is_skipped(shelf):
    write_plugin(shelf, "huge", "x" * (plugin_handler.MAX_MANIFEST_BYTES + 1))

    assert list_plugins() == []


def test_homepage_must_be_web(shelf):
    write_plugin(shelf, "rommdeck", manifest(homepage="javascript:alert(1)"))
    write_plugin(shelf, "http", manifest("http", homepage="https://romm.app"))

    plugins = {plugin.id: plugin for plugin in list_plugins()}

    assert plugins["rommdeck"].homepage is None
    assert plugins["http"].homepage == "https://romm.app"


def test_same_tab_is_kept_and_anything_else_is_a_new_tab(shelf):
    data = manifest()
    data["actions"][0]["open"] = "same-tab"
    write_plugin(shelf, "same", data)

    data = manifest("other")
    data["actions"][0]["open"] = "popup"
    write_plugin(shelf, "other", data)

    plugins = {plugin.id: plugin for plugin in list_plugins()}

    assert plugins["same"].actions[0].open == "same-tab"
    assert plugins["other"].actions[0].open == "new-tab"
