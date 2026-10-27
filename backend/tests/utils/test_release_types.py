import pytest

from utils.release_types import (
    ReleaseType,
    compute_release_types,
    release_types_from_tags,
)


@pytest.mark.parametrize(
    ("tag", "release_type"),
    [
        ("Hack", ReleaseType.HACK),
        ("hacked", ReleaseType.HACK),
        # GoodTools numbers its hacks.
        ("h", ReleaseType.HACK),
        ("h2", ReleaseType.HACK),
        ("Translation", ReleaseType.TRANSLATION),
        ("Beta", ReleaseType.PROTOTYPE),
        ("Beta 2", ReleaseType.PROTOTYPE),
        ("Proto", ReleaseType.PROTOTYPE),
        ("Prototype", ReleaseType.PROTOTYPE),
        ("Alpha", ReleaseType.PROTOTYPE),
        ("Homebrew", ReleaseType.HOMEBREW),
    ],
)
def test_a_tag_names_its_release_type(tag: str, release_type: ReleaseType):
    assert release_types_from_tags([tag]) == [release_type]


@pytest.mark.parametrize("tag", ["Rev 1", "Demo", "hackers", "Hack by Foo", "!"])
def test_other_tags_name_no_release_type(tag: str):
    assert release_types_from_tags([tag]) == []


def test_the_unlicensed_region_names_its_release_type():
    assert release_types_from_tags([], ["World", "Unlicensed"]) == [
        ReleaseType.UNLICENSED
    ]


def test_tags_yield_each_type_once_in_vocabulary_order():
    tags = ["Proto", "Hack", "h1", "Beta"]
    assert release_types_from_tags(tags, ["Unlicensed"]) == [
        ReleaseType.HACK,
        ReleaseType.PROTOTYPE,
        ReleaseType.UNLICENSED,
    ]


def test_without_a_manual_list_the_tags_and_regions_decide():
    metadata = {"tags": ["Hack"], "regions": ["Unlicensed"], "manual_metadata": {}}
    assert compute_release_types(metadata) == ["hack", "unlicensed"]
    assert compute_release_types({"tags": None, "manual_metadata": None}) == []


def test_a_manual_list_replaces_the_tags():
    metadata = {
        "tags": ["Hack"],
        "manual_metadata": {"release_types": ["translation", "color_patch"]},
    }
    assert compute_release_types(metadata) == ["color_patch", "translation"]


def test_an_empty_manual_list_falls_back_to_the_tags():
    metadata = {"tags": ["Hack"], "manual_metadata": {"release_types": []}}
    assert compute_release_types(metadata) == ["hack"]


def test_a_manual_list_drops_unknown_values():
    metadata = {"manual_metadata": {"release_types": ["fan_game", "bogus", 5]}}
    assert compute_release_types(metadata) == ["fan_game"]
