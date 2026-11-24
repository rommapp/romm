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


def test_a_panel_that_explains_no_action_is_refused(shelf):
    data = manifest()
    data["facts"] = [
        {
            "id": "handheld",
            "label": "Handheld reports",
            "url": "https://example.com/api",
            "list_path": "listings",
            "group_by": "emulator",
        }
    ]
    write_plugin(shelf, "rommdeck", data)

    # The plugin is still a plugin; the panel is what has nowhere to be drawn.
    assert list_plugins()[0].facts == []


def test_a_slot_that_is_not_a_string_is_refused_without_raising(shelf):
    data = manifest()
    data["actions"][0]["slot"] = ["game.play"]
    write_plugin(shelf, "rommdeck", data)

    # The manifest names nowhere to draw, so it adds nothing; the point is that
    # reading it does not raise and take the rest of the shelf with it.
    assert list_plugins() == []


def test_a_setting_type_that_is_not_a_string_is_refused_without_raising(shelf):
    data = manifest()
    data["settings"] = [{"key": "show", "label": "Show", "type": ["boolean"]}]
    write_plugin(shelf, "rommdeck", data)

    plugins = list_plugins()

    assert len(plugins) == 1
    assert plugins[0].settings == []


SEARCH_SOURCE = {
    "url": "https://example.com/api/devices",
    "query": {"input": '{"json":{"search":"{query}"}}'},
    "items": "result.data.json.devices",
    "value": "id",
    "label": "{brandName} {modelName}",
}


def test_a_searchable_field_keeps_where_it_asks():
    data = manifest(
        settings=[
            {
                "key": "handheld",
                "label": "Handheld",
                "type": "search",
                "source": SEARCH_SOURCE,
            }
        ]
    )

    assert data["settings"][0]["type"] == "search"
    field = plugin_handler._parse_setting(data["settings"][0], "rommdeck")

    assert field is not None
    assert field.source is not None
    assert field.source.items == "result.data.json.devices"
    assert field.source.limit == 20


def test_a_searchable_field_without_a_source_is_refused():
    field = plugin_handler._parse_setting(
        {"key": "handheld", "label": "Handheld", "type": "search"}, "rommdeck"
    )

    assert field is None


def test_a_searchable_field_naming_nothing_to_show_is_refused():
    incomplete = {key: value for key, value in SEARCH_SOURCE.items() if key != "value"}

    field = plugin_handler._parse_setting(
        {
            "key": "handheld",
            "label": "Handheld",
            "type": "search",
            "source": incomplete,
        },
        "rommdeck",
    )

    assert field is None


def test_a_searchable_field_cannot_search_a_local_address():
    field = plugin_handler._parse_setting(
        {
            "key": "handheld",
            "label": "Handheld",
            "type": "search",
            "source": {**SEARCH_SOURCE, "url": "http://127.0.0.1/devices"},
        },
        "rommdeck",
    )

    assert field is None


def test_a_group_holds_the_fields_an_entry_needs():
    field = plugin_handler._parse_setting(
        {
            "key": "setups",
            "label": "PC setups",
            "type": "groups",
            "max_items": 3,
            "fields": [
                {"key": "cpu", "label": "CPU", "type": "search", "source": SEARCH_SOURCE},
                {"key": "memory", "label": "Memory", "type": "number", "min": 1},
            ],
        },
        "rommdeck",
    )

    assert field is not None
    assert field.max_items == 3
    assert [nested.key for nested in field.fields] == ["cpu", "memory"]
    assert field.default is None


def test_a_group_inside_a_group_is_refused():
    field = plugin_handler._parse_setting(
        {
            "key": "outer",
            "label": "Outer",
            "type": "groups",
            "fields": [
                {
                    "key": "inner",
                    "label": "Inner",
                    "type": "groups",
                    "fields": [{"key": "cpu", "label": "CPU"}],
                }
            ],
        },
        "rommdeck",
    )

    assert field is None


def test_entries_a_manifest_no_longer_describes_are_dropped(shelf):
    data = manifest(
        settings=[
            {
                "key": "setups",
                "label": "PC setups",
                "type": "groups",
                "fields": [
                    {"key": "cpu", "label": "CPU"},
                    {"key": "memory", "label": "Memory", "type": "number"},
                ],
            }
        ]
    )
    write_plugin(shelf, "rommdeck", data)
    plugin = list_plugins()[0]
    kept = plugin_handler._pruned_groups(
        plugin.settings[0],
        [
            {"cpu": "c562c365", "memory": 16},
            {"cpu": "c562c365", "gpu": "gone"},
            {"memory": 8},
            "not an entry",
        ],
    )

    # What the manifest no longer describes goes, entry by entry: the second
    # entry loses its unknown field and keeps the one that is still declared.
    # The last value is not an entry at all, so nothing survives it.
    assert kept == [
        {"cpu": "c562c365", "memory": 16},
        {"cpu": "c562c365"},
        {"memory": 8},
    ]


def test_an_entry_over_the_limit_is_not_held(shelf):
    data = manifest(
        settings=[
            {
                "key": "setups",
                "label": "PC setups",
                "type": "groups",
                "max_items": 1,
                "fields": [{"key": "cpu", "label": "CPU"}],
            }
        ]
    )
    write_plugin(shelf, "rommdeck", data)
    plugin = list_plugins()[0]

    assert plugin_handler._value_fits(
        plugin.settings[0], [{"cpu": "a"}, {"cpu": "b"}]
    ) is False
    assert plugin_handler._value_fits(plugin.settings[0], [{"cpu": "a"}]) is True


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


def with_settings(**extra) -> dict:
    data = manifest()
    data["settings"] = [
        {
            "key": "bridge_url",
            "label": "Bridge URL",
            "type": "url",
            "default": "http://127.0.0.1:8050",
        },
        {
            "key": "limit",
            "label": "Streams",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 16,
        },
        {"key": "debug", "label": "Debug", "type": "boolean", "default": False},
        {
            "key": "profile",
            "label": "Profile",
            "type": "select",
            "default": "proxy",
            "options": [{"value": "proxy", "label": "Proxy"}, {"value": "direct"}],
        },
    ]
    data["settings"].append(extra) if extra else None
    return data


def test_a_manifest_describes_the_settings_its_form_shows(shelf):
    write_plugin(shelf, "rommdeck", with_settings())

    plugin = list_plugins()[0]

    assert [s.key for s in plugin.settings] == [
        "bridge_url",
        "limit",
        "debug",
        "profile",
    ]
    assert plugin.settings[0].type == "url"
    assert plugin.settings[1].min == 1
    assert [o.value for o in plugin.settings[3].options] == ["proxy", "direct"]


def test_a_setting_without_a_key_is_dropped(shelf):
    data = with_settings()
    data["settings"].append({"label": "Nowhere", "type": "text"})
    write_plugin(shelf, "rommdeck", data)

    assert len(list_plugins()[0].settings) == 4


def test_an_unknown_setting_type_drops_the_field(shelf):
    data = with_settings()
    data["settings"].append({"key": "odd", "label": "Odd", "type": "color"})
    write_plugin(shelf, "rommdeck", data)

    assert [s.key for s in list_plugins()[0].settings] == [
        "bridge_url",
        "limit",
        "debug",
        "profile",
    ]


def test_settings_start_at_the_manifests_defaults(shelf):
    write_plugin(shelf, "rommdeck", with_settings())

    values = plugin_handler.plugin_settings(list_plugins()[0])

    assert values == {
        "bridge_url": "http://127.0.0.1:8050",
        "limit": 2,
        "debug": False,
        "profile": "proxy",
    }


def test_saving_settings_writes_them_beside_the_manifest(shelf):
    write_plugin(shelf, "rommdeck", with_settings())
    plugin = list_plugins()[0]

    stored = plugin_handler.save_plugin_settings(
        plugin, {"bridge_url": "http://192.168.86.30:8050", "limit": 4, "debug": True}
    )

    assert stored["bridge_url"] == "http://192.168.86.30:8050"
    assert (shelf / "rommdeck" / "settings.json").is_file()
    assert plugin_handler.plugin_settings(plugin)["limit"] == 4
    # Left out of the form, so it keeps its default rather than vanishing.
    assert stored["profile"] == "proxy"


def test_a_setting_the_manifest_does_not_declare_is_refused(shelf):
    write_plugin(shelf, "rommdeck", with_settings())

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.save_plugin_settings(list_plugins()[0], {"nope": "x"})


@pytest.mark.parametrize(
    "values",
    [
        {"limit": "four"},
        {"limit": 99},
        {"debug": "yes"},
        {"profile": "other"},
        {"bridge_url": "not a url"},
    ],
)
def test_a_value_of_the_wrong_shape_is_refused(shelf, values):
    write_plugin(shelf, "rommdeck", with_settings())

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.save_plugin_settings(list_plugins()[0], values)


def test_a_settings_file_from_another_version_is_pruned(shelf):
    write_plugin(shelf, "rommdeck", with_settings())
    (shelf / "rommdeck" / "settings.json").write_text(
        json.dumps({"bridge_url": 5, "gone": "x", "limit": 3}), encoding="utf-8"
    )

    values = plugin_handler.plugin_settings(list_plugins()[0])

    assert values["bridge_url"] == "http://127.0.0.1:8050"  # wrong type, default kept
    assert values["limit"] == 3
    assert "gone" not in values


def test_an_action_can_be_switched_by_a_boolean_setting(shelf):
    data = with_settings()
    data["actions"][0]["enabled_by"] = "debug"
    write_plugin(shelf, "rommdeck", data)

    assert list_plugins()[0].actions[0].enabled_by == "debug"


def test_an_action_switched_by_something_that_is_not_a_setting_is_ungated(shelf):
    data = with_settings()
    data["actions"][0]["enabled_by"] = "nowhere"
    write_plugin(shelf, "rommdeck", data)

    assert list_plugins()[0].actions[0].enabled_by is None


STORE = {
    "version": 1,
    "plugins": [
        {
            "id": "rommdeck",
            "name": "RommDeck",
            "version": "1.0.0",
            "description": "Open a game on the machine RommDeck manages.",
            "manifest_url": "https://example.com/rommdeck/plugin.json",
            "tags": ["launcher"],
        },
        {"id": "broken", "name": "Broken", "manifest_url": "file:///etc/passwd"},
        {"name": "No id", "manifest_url": "https://example.com/x.json"},
    ],
}


def test_the_store_lists_what_its_index_names(shelf, monkeypatch):
    monkeypatch.setattr(plugin_handler, "_fetch_json", lambda url, limit, what: STORE)

    entries = plugin_handler.store_plugins()

    assert [e.id for e in entries] == ["rommdeck"]
    assert entries[0].manifest_url == "https://example.com/rommdeck/plugin.json"
    assert entries[0].tags == ["launcher"]


def test_an_index_entry_that_is_not_a_web_url_is_skipped(shelf, monkeypatch):
    monkeypatch.setattr(plugin_handler, "_fetch_json", lambda url, limit, what: STORE)

    assert "broken" not in [e.id for e in plugin_handler.store_plugins()]


def test_installing_from_the_store_fetches_its_manifest(shelf, monkeypatch):
    calls = []

    def fetch(url, limit, what):
        calls.append(url)
        if "index" in url:
            return STORE
        return manifest()

    monkeypatch.setattr(plugin_handler, "_fetch_json", fetch)
    monkeypatch.setattr(plugin_handler, "STORE_URL", "https://example.com/index.json")

    installed = plugin_handler.install_from_store("rommdeck")

    assert installed.id == "rommdeck"
    assert calls == [
        "https://example.com/index.json",
        "https://example.com/rommdeck/plugin.json",
    ]
    assert [p.id for p in list_plugins()] == ["rommdeck"]


def test_the_store_refuses_an_id_it_does_not_list(shelf, monkeypatch):
    monkeypatch.setattr(plugin_handler, "_fetch_json", lambda url, limit, what: STORE)

    with pytest.raises(plugin_handler.PluginRefused):
        plugin_handler.install_from_store("nowhere")


def test_a_url_built_from_a_setting_is_judged_on_its_default(shelf):
    data = with_settings()
    data["actions"].append(
        {
            "id": "dashboard",
            "label": "RommDeck",
            "url": "{setting.bridge_url}/library",
            "slot": "app.nav",
        }
    )
    write_plugin(shelf, "rommdeck", data)

    actions = {a.id: a for a in list_plugins()[0].actions}

    assert actions["dashboard"].url == "{setting.bridge_url}/library"


def test_a_url_built_from_a_setting_with_no_usable_default_is_dropped(shelf):
    data = manifest()
    data["settings"] = [
        {"key": "web", "label": "Web", "type": "text", "default": "not a url"}
    ]
    data["actions"] = [
        {"id": "open", "label": "Open", "url": "{setting.web}", "slot": "app.nav"}
    ]
    write_plugin(shelf, "rommdeck", data)

    assert list_plugins() == []
