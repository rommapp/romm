"""Tests for `GET /api/roms/anniversaries` (issue #3440).

Feeds the Home widget that shows games released on today's date. The library
can hold 100k+ roms, so the endpoint must stay on
`idx_roms_generated_first_release_date` rather than walking the table: these
tests pin the behaviour, and `test_roms_anniversaries.py` pins the day-of-year
semantics against explicit dates.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import event

from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_engine, sync_session
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _dated_rom(platform: Platform, name: str, released: date) -> Rom:
    """Seed a rom whose `generated_first_release_date` lands on `released`.

    The generated column is derived from the provider blobs, and IGDB reports
    seconds, so that is what goes in (0098 multiplies it up to milliseconds).
    """
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    seconds = int(
        datetime(
            released.year, released.month, released.day, tzinfo=timezone.utc
        ).timestamp()
    )
    return db_rom_handler.update_rom(
        rom.id, {"igdb_metadata": {"first_release_date": str(seconds)}}
    )


def _today() -> date:
    """The day the endpoint falls back to when the client sends no month/day."""
    return datetime.now(timezone.utc).date()


@pytest.fixture
def other_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(
            name="other_platform",
            slug="other_platform_slug",
            fs_slug="other_platform_slug",
        )
    )


@pytest.fixture
def captured_sql() -> Iterator[list[str]]:
    """Every statement the engine runs while the fixture is active."""
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


def _get(client: TestClient, token: str, **params):
    return client.get(
        "/api/roms/anniversaries",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )


def test_requires_auth(client: TestClient) -> None:
    assert (
        client.get("/api/roms/anniversaries").status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_returns_roms_released_on_the_requested_day(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    _dated_rom(platform, "match", date(1994, 9, 8))
    _dated_rom(platform, "miss", date(1994, 9, 9))

    response = _get(client, access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [rom["name"] for rom in body] == ["match"]
    # The widget renders cover, platform and "N years ago" straight off the row.
    assert body[0]["platform_slug"] == platform.slug
    assert body[0]["metadatum"]["first_release_date"] == 778982400000


def test_defaults_to_todays_utc_date(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """Clients send their own local date; omitting it falls back to UTC."""
    today = _today()
    _dated_rom(platform, "match", today.replace(year=today.year - 10))
    _dated_rom(platform, "miss", (today + timedelta(days=1)).replace(year=1999))

    response = _get(client, access_token)

    assert response.status_code == status.HTTP_200_OK
    assert [rom["name"] for rom in response.json()] == ["match"]


def test_orders_oldest_release_first(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The biggest anniversary leads."""
    _dated_rom(platform, "newer", date(2005, 9, 8))
    _dated_rom(platform, "older", date(1985, 9, 8))

    response = _get(client, access_token, month=9, day=8)

    assert [rom["name"] for rom in response.json()] == ["older", "newer"]


def test_january_first_is_never_an_anniversary(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """Year-only metadata from several providers all lands on 1 January."""
    _dated_rom(platform, "year_only", date(1983, 1, 1))

    response = _get(client, access_token, month=1, day=1)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_a_day_with_no_matches_is_not_an_error(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The widget shows its own empty copy, so an empty day is a 200."""
    _dated_rom(platform, "elsewhere", date(1994, 3, 3))

    response = _get(client, access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_undated_roms_are_not_returned(
    client: TestClient, access_token: str, rom: Rom
) -> None:
    """A library nothing has matched yet has no anniversaries, not an error."""
    response = _get(client, access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_returns_every_match_for_the_day(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """Under the ceiling the whole day comes back, so the counter is a real total."""
    for year in range(1970, 2000):
        _dated_rom(platform, f"rom_{year}", date(year, 9, 8))

    response = _get(client, access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    assert [rom["name"] for rom in response.json()] == [
        f"rom_{year}" for year in range(1970, 2000)
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"month": 13, "day": 1},
        {"month": 0, "day": 1},
        {"month": 9, "day": 32},
    ],
)
def test_rejects_out_of_range_parameters(
    client: TestClient, access_token: str, params: dict
) -> None:
    assert (
        _get(client, access_token, **params).status_code
        == status.HTTP_422_UNPROCESSABLE_CONTENT
    )


def test_a_client_behind_utc_does_not_get_its_own_years_release(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The client is still on 31 December while the server has entered 1 January.

    The client sends only a month and a day, so the year the query stops at has
    to follow the day it asked for rather than the server's own calendar.
    """
    _dated_rom(platform, "released_today", date(2026, 12, 31))
    _dated_rom(platform, "new_years_eve", date(1999, 12, 31))

    with patch("endpoints.roms.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2027, 1, 1, 2, tzinfo=timezone.utc)
        response = _get(client, access_token, month=12, day=31)

    assert response.status_code == status.HTTP_200_OK
    assert [rom["name"] for rom in response.json()] == ["new_years_eve"]


def test_a_day_no_year_has_returns_nothing(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """30 February is in range for both params but exists in no year."""
    _dated_rom(platform, "february", date(1994, 2, 28))

    response = _get(client, access_token, month=2, day=30)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_skips_hidden_roms(
    client: TestClient,
    viewer_user: User,
    viewer_access_token: str,
    platform: Platform,
) -> None:
    hidden = _dated_rom(platform, "hidden", date(1994, 9, 8))
    _dated_rom(platform, "visible", date(1995, 9, 8))
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=hidden.id, user_id=viewer_user.id
            )
        )

    response = _get(client, viewer_access_token, month=9, day=8)

    assert [rom["name"] for rom in response.json()] == ["visible"]


def test_skips_hidden_platforms_even_as_the_only_match(
    client: TestClient,
    viewer_user: User,
    viewer_access_token: str,
    other_platform: Platform,
) -> None:
    _dated_rom(other_platform, "on_hidden_platform", date(1994, 9, 8))
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.PLATFORMS,
                entity_id=other_platform.id,
                user_id=viewer_user.id,
            )
        )

    response = _get(client, viewer_access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_rechecks_visibility_after_fetching(
    client: TestClient,
    viewer_user: User,
    viewer_access_token: str,
    platform: Platform,
) -> None:
    """Rows are re-checked against what came back, not the filter that chose them.

    Ids are picked by a filtered query but fetched by raw id, so a rom that moved
    to a hidden platform in between was picked under its old one. Standing in for
    that race by handing the endpoint an id the filter would have excluded.
    """
    visible = _dated_rom(platform, "visible", date(1994, 9, 8))
    hidden = _dated_rom(platform, "hidden", date(1995, 9, 8))
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=hidden.id, user_id=viewer_user.id
            )
        )

    with patch.object(
        db_rom_handler,
        "get_anniversary_rom_ids",
        return_value=[visible.id, hidden.id],
    ):
        response = _get(client, viewer_access_token, month=9, day=8)

    assert response.status_code == status.HTTP_200_OK
    assert [rom["name"] for rom in response.json()] == ["visible"]


def test_does_not_page_or_count(
    client: TestClient,
    access_token: str,
    platform: Platform,
    captured_sql: list[str],
) -> None:
    """The point of the range union: cost that tracks matches, not library size.

    An OFFSET would step over every preceding row and a total would be its own
    count of the library; the union reads only the index entries it matches.
    """
    for year in range(1990, 1996):
        _dated_rom(platform, f"rom_{year}", date(year, 9, 8))
    captured_sql.clear()

    with patch.object(
        db_rom_handler, "get_rom_count", wraps=db_rom_handler.get_rom_count
    ) as get_rom_count:
        response = _get(client, access_token, month=9, day=8)
        assert response.status_code == status.HTTP_200_OK
        get_rom_count.assert_not_called()

    rom_queries = [sql for sql in captured_sql if " roms" in sql.lower()]
    assert rom_queries, "expected the lookup to query the roms table"
    assert not [sql for sql in rom_queries if "offset" in sql.lower()]
