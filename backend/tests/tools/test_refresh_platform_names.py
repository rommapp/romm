import re

from tools.refresh_platform_names import (
    IGDB_ENTRY_RE,
    rewrite_igdb_entry,
    rewrite_ss_list,
    ss_system_names,
)

SS_LIST = """SCREENSAVER_PLATFORM_LIST: dict[UPS, SlugToSSId] = {
    UPS.GENESIS: {"id": 1, "name": "Megadrive"},
    UPS.ARCADE: {
        "id": ARCADE_SS_ID,
        "name": "Arcade",
    },
    # Win9x shares the Windows system.
    UPS.WIN: {"id": 138, "name": "PC Windows"},
    UPS.WIN9X: {"id": 138, "name": "PC Win9X"},
    UPS.NGC: {"id": 13, "name": "GameCube", "alternative_names": ["Old"]},
}"""

IGDB_ENTRY = """    UPS.PS2: {
        "abbreviation": "Old",
        "category": "Console",
        "id": 8,
        "name": "PlayStation 2",
    },
"""


def test_ss_system_names_reads_regional_then_common_names_once() -> None:
    noms = {
        "nom_eu": "Megadrive",
        "nom_us": "Genesis",
        "nom_recalbox": "megadrive",
        "noms_commun": "Megadrive, Genesis,Mega Drive,",
    }

    assert ss_system_names(noms) == ["Megadrive", "Genesis", "Mega Drive"]


def test_rewrite_ss_list_adds_names_other_than_the_entry_name() -> None:
    text = rewrite_ss_list(
        SS_LIST,
        {"ARCADE_SS_ID": "75"},
        {1: ["Megadrive", "Genesis"], 75: ["Arcade"], 138: ["Windows"], 13: []},
    )

    assert (
        '    UPS.GENESIS: {"id": 1, "name": "Megadrive", "alternative_names": ["Genesis"]},\n'
        in text
    )
    # The entry name is not repeated, and the constant id is kept as written.
    assert '    UPS.ARCADE: {"id": ARCADE_SS_ID, "name": "Arcade"},\n' in text
    # A shared system's names are left off both platforms.
    assert '"Windows"' not in text
    assert "# Win9x shares the Windows system." in text
    # An emptied system drops its stale names.
    assert '    UPS.NGC: {"id": 13, "name": "GameCube"},\n' in text


def test_rewrite_ss_list_keeps_systems_screenscraper_left_out() -> None:
    assert rewrite_ss_list(SS_LIST, {"ARCADE_SS_ID": "75"}, {}) == SS_LIST


def _rewrite_igdb(names: dict[int, dict[str, str]]) -> str:
    return IGDB_ENTRY_RE.sub(lambda m: rewrite_igdb_entry(m, names), IGDB_ENTRY)


def test_rewrite_igdb_entry_replaces_the_names() -> None:
    text = _rewrite_igdb({8: {"abbreviation": "PS2", "alternative_name": "Sony PS2"}})

    assert re.findall(r'"(abbreviation|alternative_name)": "([^"]*)"', text) == [
        ("abbreviation", "PS2"),
        ("alternative_name", "Sony PS2"),
    ]
    assert '"category": "Console"' in text


def test_rewrite_igdb_entry_keeps_platforms_igdb_left_out() -> None:
    assert _rewrite_igdb({}) == IGDB_ENTRY
