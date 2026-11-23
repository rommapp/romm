import json
from pathlib import Path

import pytest
from handler import plugin_handler
from handler.plugin_handler import list_plugins


def write_plugin(base: Path, folder: str, manifest: dict | str) -> Path:
    """Write one plugin folder and answer the manifest path it wrote."""
    path = base / folder
    path.mkdir(parents=True)
    text = manifest if isinstance(manifest, str) else json.dumps(manifest)
    manifest_path = path / plugin_handler.MANIFEST_NAME
    manifest_path.write_text(text, encoding="utf-8")
    return manifest_path


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
    data = manifest("same")
    data["actions"][0]["open"] = "same-tab"
    write_plugin(shelf, "same", data)

    data = manifest("other")
    data["actions"][0]["open"] = "popup"
    write_plugin(shelf, "other", data)

    plugins = {plugin.id: plugin for plugin in list_plugins()}

    assert plugins["same"].actions[0].open == "same-tab"
    assert plugins["other"].actions[0].open == "new-tab"


def test_an_action_can_name_the_platforms_it_is_offered_on(shelf):
    data = manifest()
    data["actions"][0]["platforms"] = ["NGC", "wii", "ngc"]
    write_plugin(shelf, "rommdeck", data)

    action = list_plugins()[0].actions[0]

    assert action.platforms == ["ngc", "wii"]


def test_an_action_without_platforms_is_offered_everywhere(shelf):
    write_plugin(shelf, "rommdeck", manifest())

    assert list_plugins()[0].actions[0].platforms == []


@pytest.mark.parametrize(
    "platforms",
    ["ngc", [1], [""], ["no spaces allowed"], ["ok"] * 65],
)
def test_a_malformed_platform_list_drops_the_action(shelf, platforms):
    data = manifest()
    data["actions"][0]["platforms"] = platforms
    write_plugin(shelf, "rommdeck", data)

    assert list_plugins() == []


def test_an_image_is_kept_only_when_it_is_a_web_url(shelf):
    data = manifest("web")
    data["actions"][0]["image"] = "https://example.com/logo.png"
    write_plugin(shelf, "web", data)

    data = manifest("bad")
    data["actions"][0]["image"] = "javascript:alert(1)"
    write_plugin(shelf, "bad", data)

    plugins = {plugin.id: plugin for plugin in list_plugins()}

    assert plugins["web"].actions[0].image == "https://example.com/logo.png"
    assert plugins["bad"].actions[0].image is None


def test_an_action_without_a_slot_lands_on_the_game(shelf):
    write_plugin(shelf, "rommdeck", manifest())

    assert list_plugins()[0].actions[0].slot == "game.details"


def test_a_named_slot_is_kept(shelf):
    data = manifest("nav")
    data["actions"][0]["slot"] = "app.nav"
    write_plugin(shelf, "nav", data)

    assert list_plugins()[0].actions[0].slot == "app.nav"


def test_a_legacy_play_flag_means_the_play_slot(shelf):
    data = manifest("playable")
    data["actions"][0]["play"] = True
    write_plugin(shelf, "playable", data)

    assert list_plugins()[0].actions[0].slot == "game.play"


@pytest.mark.parametrize("slot", ["game.sidebar", "", 7])
def test_an_unknown_slot_drops_the_action(shelf, slot):
    data = manifest("nowhere")
    data["actions"][0]["slot"] = slot
    write_plugin(shelf, "nowhere", data)

    assert list_plugins() == []


def test_a_parked_plugin_adds_nothing(shelf):
    write_plugin(shelf, "rommdeck", manifest(enabled=False))

    assert list_plugins() == []


def test_an_enabled_plugin_is_listed(shelf):
    write_plugin(shelf, "rommdeck", manifest(enabled=True))

    assert [plugin.id for plugin in list_plugins()] == ["rommdeck"]


def test_a_folder_without_a_manifest_is_not_a_plugin(shelf):
    (shelf / "notes").mkdir()
    write_plugin(shelf, "rommdeck", manifest())

    assert [plugin.id for plugin in list_plugins()] == ["rommdeck"]


def test_a_manifest_symlinked_out_of_the_shelf_is_refused(shelf, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "plugin.json"
    outside.write_text(json.dumps(manifest()), encoding="utf-8")
    folder = shelf / "rommdeck"
    folder.mkdir()
    (folder / plugin_handler.MANIFEST_NAME).symlink_to(outside)

    assert list_plugins() == []


def test_a_manifest_in_place_is_read_again_once_it_changes(shelf):
    path = write_plugin(shelf, "rommdeck", manifest())
    assert list_plugins()[0].name == "RommDeck"

    renamed = manifest(name="RommDeck Two")
    path.write_text(json.dumps(renamed), encoding="utf-8")

    assert list_plugins()[0].name == "RommDeck Two"


def test_installing_from_a_manifest_writes_it_to_the_shelf(shelf):
    installed = plugin_handler.install_plugin(manifest=manifest())

    assert installed.id == "rommdeck"
    assert (shelf / "rommdeck" / "plugin.json").is_file()
    assert [plugin.id for plugin in list_plugins()] == ["rommdeck"]


def test_installing_twice_is_refused(shelf):
    plugin_handler.install_plugin(manifest=manifest())

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.install_plugin(manifest=manifest())


def test_a_manifest_without_an_id_is_refused(shelf):
    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.install_plugin(manifest={"name": "No id"})


def test_a_manifest_the_reader_would_refuse_is_not_stored(shelf):
    data = manifest()
    data["actions"][0]["url"] = "javascript:alert(1)"

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.install_plugin(manifest=data)

    assert list(shelf.iterdir()) == []


def test_a_non_http_url_is_not_fetched(shelf):
    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.install_plugin(url="file:///etc/passwd")

    assert list(shelf.iterdir()) == []


def test_removing_a_plugin_takes_its_folder(shelf):
    plugin_handler.install_plugin(manifest=manifest())

    plugin_handler.remove_plugin("rommdeck")

    assert list_plugins() == []
    assert not (shelf / "rommdeck").exists()


def test_removing_something_that_is_not_there_is_refused(shelf):
    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.remove_plugin("absent")


def test_a_traversal_id_cannot_be_removed(shelf):
    outside = shelf.parent / "elsewhere"
    outside.mkdir()
    (outside / "plugin.json").write_text(json.dumps(manifest()), encoding="utf-8")

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.remove_plugin("../elsewhere")

    assert outside.exists()
