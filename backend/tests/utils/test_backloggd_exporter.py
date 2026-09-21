import csv
import io
from datetime import UTC, datetime, timedelta, timezone

import pytest

from models.rom import Rom, RomUser, RomUserStatus
from utils.backloggd_exporter import CSV_HEADER, build_csv


def _rom_user(
    name: str,
    *,
    igdb_id: int | None = None,
    release_ms: int | None = None,
    rating: int = 0,
    status: RomUserStatus | None = None,
    backlogged: bool = False,
    now_playing: bool = False,
    last_played: datetime | None = None,
) -> RomUser:
    rom = Rom(name=name, fs_name=f"{name}.zip", igdb_id=igdb_id)
    rom.generated_first_release_date = release_ms
    rom_user = RomUser(
        rating=rating,
        status=status,
        backlogged=backlogged,
        now_playing=now_playing,
        last_played=last_played,
    )
    rom_user.rom = rom
    return rom_user


def _rows(csv_content: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_content)))


def test_header_is_written_for_an_empty_export():
    assert _rows(build_csv([])) == [CSV_HEADER]


def test_row_carries_every_column():
    csv_content = build_csv(
        [
            _rom_user(
                "Chrono Trigger",
                release_ms=int(datetime(1995, 3, 11, tzinfo=UTC).timestamp() * 1000),
                rating=9,
                status=RomUserStatus.FINISHED,
                last_played=datetime(2024, 6, 1, 12, 30, tzinfo=UTC),
            )
        ]
    )

    assert _rows(csv_content)[1] == [
        "Chrono Trigger",
        "1995",
        "4.5",
        "completed",
        "2024-06-01",
    ]


@pytest.mark.parametrize(
    ("rating", "expected"),
    [(0, ""), (1, "0.5"), (5, "2.5"), (9, "4.5"), (10, "5.0")],
)
def test_rating_halves_onto_the_five_star_scale(rating: int, expected: str):
    csv_content = build_csv([_rom_user("Game", rating=rating)])

    assert _rows(csv_content)[1][2] == expected


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"status": RomUserStatus.FINISHED}, "completed"),
        ({"status": RomUserStatus.COMPLETED_100}, "completed"),
        ({"status": RomUserStatus.INCOMPLETE}, "playing"),
        ({"now_playing": True}, "playing"),
        ({"backlogged": True}, "backlog"),
        ({"status": RomUserStatus.RETIRED}, ""),
        ({"status": RomUserStatus.NEVER_PLAYING}, ""),
    ],
)
def test_status_mapping(kwargs: dict, expected: str):
    csv_content = build_csv([_rom_user("Game", **kwargs)])

    assert _rows(csv_content)[1][3] == expected


def test_explicit_status_wins_over_the_flags():
    csv_content = build_csv(
        [
            _rom_user(
                "Game",
                status=RomUserStatus.FINISHED,
                backlogged=True,
                now_playing=True,
            )
        ]
    )

    assert _rows(csv_content)[1][3] == "completed"


def test_now_playing_wins_over_backlogged():
    csv_content = build_csv([_rom_user("Game", now_playing=True, backlogged=True)])

    assert _rows(csv_content)[1][3] == "playing"


def test_siblings_collapse_to_one_row_by_igdb_id():
    # Same game, two regional dumps: Backloggd takes one log, not two.
    rows = _rows(
        build_csv(
            [
                _rom_user("Super Metroid (USA)", igdb_id=1103),
                _rom_user("Super Metroid (JPN)", igdb_id=1103, rating=10),
            ]
        )
    )

    assert len(rows) == 2
    assert rows[1][0] == "Super Metroid (JPN)"
    assert rows[1][2] == "5.0"


def test_rows_without_an_igdb_id_collapse_by_name():
    rows = _rows(
        build_csv([_rom_user("Tetris", backlogged=True), _rom_user("tetris", rating=8)])
    )

    assert len(rows) == 2
    assert rows[1][2] == "4.0"


def test_siblings_merge_field_by_field():
    # Rated one dump, played another: the single log keeps both.
    rows = _rows(
        build_csv(
            [
                _rom_user("Doom (USA)", igdb_id=7, rating=8, backlogged=True),
                _rom_user(
                    "Doom (EUR)",
                    igdb_id=7,
                    status=RomUserStatus.FINISHED,
                    last_played=datetime(2023, 5, 4, tzinfo=UTC),
                ),
            ]
        )
    )

    assert rows[1] == ["Doom (EUR)", "", "4.0", "completed", "2023-05-04"]


def test_merged_siblings_take_the_earliest_year_and_latest_play():
    rows = _rows(
        build_csv(
            [
                _rom_user(
                    "Port",
                    igdb_id=9,
                    release_ms=int(datetime(1998, 1, 1, tzinfo=UTC).timestamp() * 1000),
                    last_played=datetime(2020, 1, 1, tzinfo=UTC),
                ),
                _rom_user(
                    "Original",
                    igdb_id=9,
                    release_ms=int(datetime(1993, 1, 1, tzinfo=UTC).timestamp() * 1000),
                    last_played=datetime(2024, 9, 9, tzinfo=UTC),
                ),
            ]
        )
    )

    assert rows[1][1] == "1993"
    assert rows[1][4] == "2024-09-09"


def test_different_games_are_kept_apart():
    rows = _rows(
        build_csv(
            [
                _rom_user("Zelda", igdb_id=1),
                _rom_user("Metroid", igdb_id=2),
                _rom_user("Castlevania"),
            ]
        )
    )

    assert [row[0] for row in rows[1:]] == ["Castlevania", "Metroid", "Zelda"]


def test_unset_values_render_blank():
    assert _rows(build_csv([_rom_user("Game")]))[1] == ["Game", "", "", "", ""]


def test_epoch_release_date_counts_as_unset():
    # The roms_metadata view drops the epoch too; it is never a real date.
    assert _rows(build_csv([_rom_user("Game", release_ms=0)]))[1][1] == ""


def test_out_of_range_release_date_is_dropped_not_raised():
    assert _rows(build_csv([_rom_user("Game", release_ms=10**18)]))[1][1] == ""


def test_naive_last_played_is_read_as_utc():
    csv_content = build_csv(
        [_rom_user("Game", last_played=datetime(2024, 1, 2, 23, 0))]
    )

    assert _rows(csv_content)[1][4] == "2024-01-02"


def test_aware_last_played_is_converted_to_utc():
    # 00:30 on the 3rd at +02:00 is still the 2nd in UTC.
    csv_content = build_csv(
        [
            _rom_user(
                "Game",
                last_played=datetime(
                    2024, 1, 3, 0, 30, tzinfo=timezone(timedelta(hours=2))
                ),
            )
        ]
    )

    assert _rows(csv_content)[1][4] == "2024-01-02"


def test_unnamed_rom_falls_back_to_the_filename():
    rom_user = _rom_user("Game", rating=6)
    rom_user.rom.name = None

    assert _rows(build_csv([rom_user]))[1][0] == "Game.zip"


def test_rom_with_no_usable_name_is_skipped():
    rom_user = _rom_user("Game", rating=6)
    rom_user.rom.name = None
    rom_user.rom.fs_name = ""

    assert _rows(build_csv([rom_user])) == [CSV_HEADER]


def test_commas_in_a_title_are_quoted():
    csv_content = build_csv([_rom_user("Sonic, the Hedgehog")])

    assert '"Sonic, the Hedgehog"' in csv_content
