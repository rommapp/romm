"""Tests for the `released_days` filter on `GET /api/roms` (issue #3440).

Feeds the Home anniversary widget, which asks for one page at a time. The
library can hold 100k+ roms, so the filter must stay on
`idx_roms_generated_first_release_date` rather than walking the table; the
day-of-year semantics are pinned in `tests/handler/database/test_roms_released_days.py`.
"""

from datetime import date, datetime, timezone

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
def captured_sql():
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
    """The widget's own call shape: one page, no sidecars it never renders."""
    return client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "order_by": "first_release_date",
            "order_dir": "asc",
            "with_char_index": False,
            "with_filter_values": False,
            "with_rom_id_index": False,
            **params,
        },
    )


def _names(response) -> list[str]:
    return [rom["name"] for rom in response.json()["items"]]


def test_requires_auth(client: TestClient) -> None:
    assert (
        client.get("/api/roms", params={"released_days": "9-8"}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_returns_roms_released_on_the_requested_day(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    _dated_rom(platform, "match", date(1994, 9, 8))
    _dated_rom(platform, "miss", date(1994, 9, 9))

    response = _get(client, access_token, released_days="9-8")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert _names(response) == ["match"]
    # The widget renders cover, platform and "N years ago" straight off the row.
    assert body["items"][0]["platform_slug"] == platform.slug
    assert body["items"][0]["metadatum"]["first_release_date"] == 778982400000


def test_orders_oldest_release_first(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The biggest anniversary leads."""
    _dated_rom(platform, "newer", date(2005, 9, 8))
    _dated_rom(platform, "older", date(1985, 9, 8))

    assert _names(_get(client, access_token, released_days="9-8")) == [
        "older",
        "newer",
    ]


def test_matches_several_days_at_once(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """How the widget surfaces a leap baby on 28 February of a non-leap year."""
    _dated_rom(platform, "leap_baby", date(2004, 2, 29))
    _dated_rom(platform, "end_of_february", date(1998, 2, 28))
    _dated_rom(platform, "march", date(1998, 3, 1))

    response = _get(client, access_token, released_days=["2-28", "2-29"])

    assert _names(response) == ["end_of_february", "leap_baby"]


def test_the_year_bound_excludes_the_callers_own_year(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """A game released earlier today is not "N years ago today"."""
    _dated_rom(platform, "released_this_year", date(2026, 9, 8))
    _dated_rom(platform, "released_before", date(1999, 9, 8))

    response = _get(
        client, access_token, released_days="9-8", released_before_year=2026
    )

    assert _names(response) == ["released_before"]


def test_a_day_with_no_matches_is_not_an_error(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The widget shows its own empty copy, so an empty day is a 200."""
    _dated_rom(platform, "elsewhere", date(1994, 3, 3))

    response = _get(client, access_token, released_days="9-8")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["items"] == []


def test_undated_roms_are_not_returned(
    client: TestClient, access_token: str, rom: Rom
) -> None:
    """A library nothing has matched yet has no anniversaries, not an error."""
    response = _get(client, access_token, released_days="9-8")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["items"] == []


def test_a_day_no_year_has_returns_nothing(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """30 February parses as a day but exists in no year."""
    _dated_rom(platform, "february", date(1994, 2, 28))

    response = _get(client, access_token, released_days="2-30")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "released_days",
    ["13-1", "0-1", "9-32", "9", "9-8-2020", "september-8", "", "9-x"],
)
def test_rejects_malformed_days(
    client: TestClient, access_token: str, released_days: str
) -> None:
    """A typo fails loudly rather than quietly matching nothing."""
    assert (
        _get(client, access_token, released_days=released_days).status_code
        == status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def test_rejects_more_days_than_the_ceiling(
    client: TestClient, access_token: str
) -> None:
    """Each day widens the range union the index walks."""
    response = _get(
        client, access_token, released_days=[f"{month}-1" for month in range(1, 13)]
    )
    assert response.status_code == status.HTTP_200_OK

    too_many = _get(
        client,
        access_token,
        released_days=[f"{month}-1" for month in range(1, 13)] + ["1-2"],
    )
    assert too_many.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_pages_the_day_without_shipping_all_of_it(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The widget shows one game at a time, so it fetches a page, not the day."""
    for year in range(1990, 2000):
        _dated_rom(platform, f"rom_{year}", date(year, 9, 8))

    first = _get(client, access_token, released_days="9-8", limit=4, offset=0)
    second = _get(client, access_token, released_days="9-8", limit=4, offset=4)

    assert _names(first) == [f"rom_{year}" for year in range(1990, 1994)]
    assert _names(second) == [f"rom_{year}" for year in range(1994, 1998)]
    # The counter the widget renders is the day's real total, not the page size.
    assert first.json()["total"] == 10


def test_paging_never_repeats_a_rom_when_the_day_ties(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """Same-day releases share a timestamp, so the sort needs the id to settle it."""
    for index in range(10):
        _dated_rom(platform, f"rom_{index}", date(1994, 9, 8))

    seen: list[str] = []
    for offset in range(0, 10, 2):
        seen += _names(
            _get(client, access_token, released_days="9-8", limit=2, offset=offset)
        )

    assert sorted(seen) == sorted(f"rom_{index}" for index in range(10))


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

    response = _get(client, viewer_access_token, released_days="9-8")

    assert _names(response) == ["visible"]


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

    response = _get(client, viewer_access_token, released_days="9-8")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["items"] == []


def test_the_filtered_page_is_not_served_from_the_unscoped_cache(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """The sidecar cache key encodes no filters, so a narrowed list must not reuse it.

    Asking for the whole library first primes the unscoped key; the filtered
    request that follows has to compute its own rom id index.
    """
    _dated_rom(platform, "match", date(1994, 9, 8))
    _dated_rom(platform, "miss", date(1994, 9, 9))

    unscoped = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"with_rom_id_index": True, "with_filter_values": False},
    )
    assert len(unscoped.json()["rom_id_index"]) == 2

    filtered = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "released_days": "9-8",
            "with_rom_id_index": True,
            "with_filter_values": False,
        },
    )

    assert [rom["name"] for rom in filtered.json()["items"]] == ["match"]
    assert len(filtered.json()["rom_id_index"]) == 1


def test_the_day_lookup_stays_on_the_index(
    client: TestClient,
    access_token: str,
    platform: Platform,
    captured_sql: list[str],
) -> None:
    """The point of the range union: no SQL date function on the indexed column."""
    for year in range(1990, 1996):
        _dated_rom(platform, f"rom_{year}", date(year, 9, 8))
    captured_sql.clear()

    response = _get(client, access_token, released_days="9-8", limit=1)
    assert response.status_code == status.HTTP_200_OK

    rom_queries = [sql for sql in captured_sql if " roms" in sql.lower()]
    assert rom_queries, "expected the lookup to query the roms table"
    assert not [
        sql
        for sql in rom_queries
        if "month(" in sql.lower() or "dayofmonth(" in sql.lower()
    ]
