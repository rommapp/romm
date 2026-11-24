"""The choices a searchable setting offers.

Nothing here reaches the network: the fetch is replaced with a function that
answers from a dictionary, so what is under test is the part that is ours — how
the query is substituted, how an answer is read, and what a missing source looks
like to a form.
"""

import pytest
from endpoints.responses.plugin import (
    PluginOptionSourceSchema,
    PluginSettingSchema,
)
from handler import plugin_options
from handler.plugin_handler import PluginRefused

DEVICES = {
    "result": {
        "data": {
            "json": {
                "devices": [
                    {
                        "id": "82f3e2fe",
                        "brandName": "AYANEO",
                        "modelName": "KONKR Pocket FIT",
                    },
                    {"id": "e4394fe4", "brandName": "AYN", "modelName": "Thor Max"},
                    {"id": "e4394fe4", "brandName": "AYN", "modelName": "Thor Max"},
                    {"id": "", "brandName": "Nobody", "modelName": "Nameless"},
                ]
            }
        }
    }
}


def source(**overrides) -> PluginOptionSourceSchema:
    values: dict = {
        "url": "https://example.com/api/devices",
        "query": {"input": '{"json":{"search":"{query}","limit":20}}'},
        "items": "result.data.json.devices",
        "value": "id",
        "label": "{brandName} {modelName}",
        "limit": 20,
    }
    values.update(overrides)
    return PluginOptionSourceSchema(**values)


def setting(**overrides) -> PluginSettingSchema:
    values: dict = {
        "key": "handheld",
        "label": "Handheld",
        "type": "search",
        "source": source(),
    }
    values.update(overrides)
    return PluginSettingSchema(**values)


class Plugin:
    """Stand-in for the parsed plugin: the options code only reads settings."""

    def __init__(self, *fields: PluginSettingSchema) -> None:
        self.id = "emuready"
        self.name = "EmuReady"
        self.settings = list(fields)


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch):
    """Answer every fetch from a dictionary, and record what was asked."""
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_fetch(url: str, params: dict[str, str]):
        calls.append((url, params))
        return DEVICES

    monkeypatch.setattr(plugin_options, "_fetch", fake_fetch)
    plugin_options._CACHE.clear()
    return calls


def test_a_search_offers_what_the_source_has(asked: list) -> None:
    options, note = plugin_options.options_for(Plugin(setting()), "handheld", "pocket")

    assert note is None
    assert [(o.value, o.label) for o in options] == [
        ("82f3e2fe", "AYANEO KONKR Pocket FIT"),
        ("e4394fe4", "AYN Thor Max"),
    ]


def test_the_query_is_substituted_once(asked: list) -> None:
    plugin_options.options_for(Plugin(setting()), "handheld", "Luigi's Mansion")

    sent = asked[0][1]["input"]
    assert '"search":"Luigi\'s Mansion"' in sent
    # Percent-encoding belongs to the client that sends it, not to the value.
    assert "%25" not in sent
    assert "\\u" not in sent


def test_a_quote_in_the_query_does_not_break_the_template(asked: list) -> None:
    plugin_options.options_for(Plugin(setting()), "handheld", 'a "quoted" name')

    sent = asked[0][1]["input"]
    assert '"search":"a \\"quoted\\" name"' in sent


def test_an_entry_without_a_value_or_a_name_is_not_offered(asked: list) -> None:
    options, _ = plugin_options.options_for(Plugin(setting()), "handheld", "")

    assert len(options) == 2
    assert all(o.value and o.label for o in options)


def test_a_plain_path_names_an_entry(asked: list) -> None:
    plain = setting(source=source(label="modelName"))

    options, _ = plugin_options.options_for(Plugin(plain), "handheld", "")

    assert options[0].label == "KONKR Pocket FIT"


def test_the_limit_bounds_what_is_offered(asked: list) -> None:
    short = setting(source=source(limit=1))

    options, _ = plugin_options.options_for(Plugin(short), "handheld", "")

    assert len(options) == 1


def test_a_source_that_cannot_be_asked_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(url: str, params: dict[str, str]):
        raise PluginRefused("https://example.com answered 500")

    monkeypatch.setattr(plugin_options, "_fetch", refuse)
    plugin_options._CACHE.clear()

    options, note = plugin_options.options_for(Plugin(setting()), "handheld", "")

    assert options == []
    assert note == "https://example.com answered 500"


def test_a_reply_of_the_wrong_shape_is_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_options, "_fetch", lambda url, params: {"nothing": 1})
    plugin_options._CACHE.clear()

    options, note = plugin_options.options_for(Plugin(setting()), "handheld", "")

    assert options == []
    assert note is not None and "not a list" in note


def test_a_search_is_asked_once_per_query(asked: list) -> None:
    plugin = Plugin(setting())
    plugin_options.options_for(plugin, "handheld", "retroid")
    plugin_options.options_for(plugin, "handheld", "retroid")

    assert len(asked) == 1


def test_a_field_that_is_not_searchable_is_refused(asked: list) -> None:
    plain = Plugin(PluginSettingSchema(key="name", label="Name"))

    with pytest.raises(PluginRefused):
        plugin_options.options_for(plain, "name", "")


def test_a_field_inside_a_group_can_be_searched(asked: list) -> None:
    group = PluginSettingSchema(
        key="setups",
        label="Setups",
        type="groups",
        fields=[setting(key="cpu", label="CPU")],
    )

    options, note = plugin_options.options_for(
        Plugin(group), "cpu", "thor"
    )

    assert note is None
    assert len(options) == 2
