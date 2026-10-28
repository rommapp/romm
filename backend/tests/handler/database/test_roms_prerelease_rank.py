"""The pre-release rank that orders a sibling group's versions: a tag counts only right after "("."""

import re

import pytest
from sqlalchemy import select
from tests.conftest import engine  # noqa: F401  (loads the test database setup)
from tests.factories import make_rom
from tests.sql_dialects import MARIADB_DIALECT, POSTGRESQL_DIALECT, compile_sql

from handler.database.base_handler import sync_session
from handler.database.roms_handler import _PRERELEASE_PATTERN, _prerelease_rank
from models.base import PRERELEASE_FILENAME_TAGS
from models.platform import Platform
from models.rom import Rom


def _ilike_rule(name: str) -> bool:
    """What the PostgreSQL ILIKEs match: the lowercase name contains "(" plus a tag."""
    return any(f"({tag}" in name.lower() for tag in PRERELEASE_FILENAME_TAGS)


NAMES = [
    "Game (USA)",
    "Game (Demo)",
    "Game (DEMO) (USA)",
    "Game (Demo Kiosk)",
    "Game (Beta 2)",
    "Game (Proto)",
    "Game (Prototype)",
    "Game (Sample)",
    "Game (Kiosk)",
    "Game (Preview)",
    "Game (Europe) (Beta)",
    "Demolition Man (USA)",
    "Beta Fish (USA)",
    "Game [Preview]",
    "Game - Demo Edition",
    "Game (Rev 1)",
    "",
]


@pytest.mark.parametrize("name", NAMES)
def test_the_regex_agrees_with_the_ilike_rule(name: str):
    matches = bool(re.search(_PRERELEASE_PATTERN, name, re.IGNORECASE))

    assert matches == _ilike_rule(name)


def test_mariadb_matches_one_regex_per_row():
    sql = compile_sql(select(_prerelease_rank()), MARIADB_DIALECT).lower()

    assert sql.count("regexp") == 1
    assert "like" not in sql


def test_postgresql_keeps_one_ilike_per_tag():
    sql = compile_sql(select(_prerelease_rank()), POSTGRESQL_DIALECT).lower()

    assert sql.count("ilike") == len(PRERELEASE_FILENAME_TAGS)
    assert "~*" not in sql


@pytest.mark.parametrize(
    ("stem", "rank"),
    [
        ("Game One (USA)", 0),
        ("Game Two (Demo)", 1),
        # Upper case: the match must be case-insensitive on this database too.
        ("GAME THREE (DEMO) (USA)", 1),
        ("Game Four (Beta 2)", 1),
        ("Game Five (Prototype)", 1),
        ("Game Six (Kiosk Demo)", 1),
        # A tag counts only right after "(".
        ("Demolition Man (USA)", 0),
        ("Beta Fish (USA)", 0),
    ],
)
def test_the_rank_on_a_real_row(platform: Platform, stem: str, rank: int):
    """Runs on whichever database the suite uses, so the engine's own regex decides."""
    rom = make_rom(platform, stem)

    with sync_session.begin() as session:
        result = session.scalar(select(_prerelease_rank()).where(Rom.id == rom.id))

    assert result == rank
