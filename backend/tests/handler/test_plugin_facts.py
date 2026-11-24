"""The panels a plugin fills from its own source.

Nothing here reaches the network: the fetch is replaced with a transport that
answers from a dictionary, so what is under test is the part that is ours —
which manifests are allowed, how an answer is read, and what a failing source
looks like to the page.
"""

import json

import pytest
from handler import plugin_facts
from handler.plugin_facts import (
    PluginFactSpec,
    expand_query,
    fill_fact,
    refused_source,
    source_url,
    still_worth_drawing,
)
from handler.plugin_handler import expand_template

LISTINGS = {
    "result": {
        "data": {
            "json": {
                "listings": [
                    {
                        "emulator": {"name": "Dolphin"},
                        "performance": {"label": "Perfect"},
                    },
                    {
                        "emulator": {"name": "Dolphin"},
                        "performance": {"label": "Great"},
                    },
                    {
                        "emulator": {"name": "Dolphin"},
                        "performance": {"label": "Perfect"},
                    },
                    {
                        "emulator": {"name": "RetroArch"},
                        "performance": {"label": "Playable"},
                    },
                ]
            }
        }
    }
}


def spec(**overrides) -> PluginFactSpec:
    values: dict = {
        "id": "handheld",
        "label": "Handheld reports",
        "slot": "game.details",
        "url": "https://example.com/api",
        "list_path": "result.data.json.listings",
        "group_by": "emulator.name",
        "rating_field": "performance.label",
    }
    values.update(overrides)
    return PluginFactSpec(**values)


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch):
    """Answer every fetch from a dictionary, and record what was asked for."""

    calls: list[str] = []

    def fake_fetch(url: str) -> dict:
        calls.append(url)
        return LISTINGS

    def fake_refused(url: str):
        return None

    monkeypatch.setattr(plugin_facts, "_fetch", fake_fetch)
    monkeypatch.setattr(plugin_facts, "refused_source", fake_refused)
    plugin_facts.forget_all()
    return calls


def test_counts_one_group_per_emulator(source: list[str]) -> None:
    fact = fill_fact("emuready", spec(), "https://example.com/api", None)

    assert fact.note is None
    assert fact.total == 4
    assert [group.key for group in fact.groups] == ["Dolphin", "RetroArch"]
    assert fact.groups[0].counts == {"Perfect": 2, "Great": 1}
    assert fact.groups[1].counts == {"Playable": 1}


def test_a_source_is_asked_for_once_per_answer(source: list[str]) -> None:
    fill_fact("emuready", spec(), "https://example.com/api?x=1", None)
    fill_fact("emuready", spec(), "https://example.com/api?x=1", None)

    assert len(source) == 1


def test_a_title_nobody_reported_on_says_so(source: list[str]) -> None:
    empty = {"result": {"data": {"json": {"listings": []}}}}
    plugin_facts._fetch = lambda url: empty  # type: ignore[assignment]

    fact = fill_fact("emuready", spec(), "https://example.com/api", None)

    assert fact.groups == []
    assert fact.note == "No reports for this title yet"


def test_an_answer_in_another_shape_is_explained(source: list[str]) -> None:
    plugin_facts._fetch = lambda url: {"unexpected": True}  # type: ignore[assignment]

    fact = fill_fact("emuready", spec(), "https://example.com/api", None)

    assert fact.note is not None
    assert "shape" in fact.note


def test_a_failing_source_is_a_note_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(url: str) -> dict:
        raise ValueError("The source answered 503")

    monkeypatch.setattr(plugin_facts, "_fetch", failing)
    monkeypatch.setattr(plugin_facts, "refused_source", lambda url: None)
    plugin_facts.forget_all()

    fact = fill_fact("emuready", spec(), "https://example.com/api", None)

    assert fact.note == "The source answered 503"
    assert fact.groups == []


def test_the_link_is_carried_through(source: list[str]) -> None:
    fact = fill_fact(
        "emuready", spec(), "https://example.com/api", "https://example.com/listings"
    )

    assert fact.link == "https://example.com/listings"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/admin",
        "http://localhost/api",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_a_manifest_cannot_read_the_machine_it_runs_on(url: str) -> None:
    assert refused_source(url) is not None


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.com/x", "not a url"]
)
def test_only_http_sources_are_fetched(url: str) -> None:
    assert refused_source(url) is not None


def test_a_public_source_is_allowed() -> None:
    assert refused_source("https://www.emuready.com/api") is None


def test_a_gated_panel_is_skipped_only_when_switched_off() -> None:
    gated = spec(enabled_by="show_handheld")

    assert still_worth_drawing(gated, {"show_handheld": False}) is False
    assert still_worth_drawing(gated, {"show_handheld": True}) is True
    assert still_worth_drawing(gated, {}) is True


def test_a_query_value_is_left_raw_for_the_query_builder() -> None:
    expanded = expand_template(
        '{"json":{"search":"{rom_name}"}}',
        {"rom_name": "Luigi's Mansion"},
        {},
    )

    assert expanded == '{"json":{"search":"Luigi\'s Mansion"}}'


def test_a_query_is_encoded_once() -> None:
    query = expand_query({"input": json.dumps({"json": {"search": "Luigi's Mansion"}})})

    assert (
        "%27" in query or "Luigi%27s" in query or "Luigi%27" in query or "%22" in query
    )
    assert " " not in query


def test_a_base_url_that_already_has_a_query_keeps_it() -> None:
    assert (
        source_url("https://example.com/api?v=2", "x=1")
        == "https://example.com/api?v=2&x=1"
    )
    assert source_url("https://example.com/api", "x=1") == "https://example.com/api?x=1"
    assert source_url("https://example.com/api", "") == "https://example.com/api"


def test_the_game_and_its_settings_fill_a_template() -> None:
    values = {
        "rom_id": "42",
        "rom_name": "Luigi's Mansion",
        "platform_slug": "ngc",
        "platform_name": "Nintendo GameCube",
        "file_name": "Luigi's Mansion (USA).iso",
    }

    expanded = expand_template(
        "{setting.base}/listings?search={rom_name}&platform={platform_slug}",
        values,
        {"base": "https://www.emuready.com"},
        encode_rom=True,
    )

    assert expanded == (
        "https://www.emuready.com/listings?search=Luigi%27s%20Mansion&platform=ngc"
    )
