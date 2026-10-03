from pathlib import Path

from handler.easyrpg import (
    EasyRpgHandler,
    build_index,
    easyrpg_handler,
    normalize_name,
)

RTP_TABLE = {
    "music": [["戦闘1", "battle 1", "battle1"]],
    "system": [["システム", "system"]],
}


def test_root_files_keep_their_extension():
    index = build_index(["RPG_RT.ldb", "RPG_RT.lmt", "Map0001.lmu"], {}, {})

    assert index["metadata"]["version"] == 2
    assert index["cache"] == {
        "rpg_rt.ldb": "RPG_RT.ldb",
        "rpg_rt.lmt": "RPG_RT.lmt",
        "map0001.lmu": "Map0001.lmu",
    }


def test_folder_files_drop_their_extension_except_ini_and_po():
    cache = build_index(
        ["ChipSet/World.png", "Language/Meta.ini", "Language/de.po"], {}, {}
    )["cache"]

    assert cache["chipset"] == {"_dirname": "ChipSet", "world": "World.png"}
    assert cache["language"] == {
        "_dirname": "Language",
        "meta.ini": "Meta.ini",
        "de.po": "de.po",
    }


def test_exfont_is_keyed_without_its_extension():
    cache = build_index(["ExFont.png"], {}, {})["cache"]

    assert cache == {"exfont": "ExFont.png"}


def test_keys_are_lowercased_and_width_normalized():
    cache = build_index(["Ｍｕｓｉｃ/Ｔｏｗｎ.mid"], {}, {})["cache"]

    assert cache["music"] == {"_dirname": "Ｍｕｓｉｃ", "town": "Ｔｏｗｎ.mid"}


def test_nested_folders_nest_in_the_index():
    cache = build_index(["Language/de/Picture/Title.png"], {}, {})["cache"]

    assert cache["language"]["de"]["picture"] == {
        "_dirname": "Picture",
        "title": "Title.png",
    }


def test_rtp_assets_answer_to_every_translated_name():
    cache = build_index(["RPG_RT.ldb"], {"Music": ["Battle 1.mid"]}, RTP_TABLE)["cache"]

    assert cache["music"] == {
        "_dirname": "Music",
        "戦闘1": "Battle 1.mid",
        "battle 1": "Battle 1.mid",
        "battle1": "Battle 1.mid",
    }


def test_rtp_assets_join_the_games_folder_under_its_spelling():
    cache = build_index(["music/Town.mid"], {"Music": ["Battle 1.mid"]}, RTP_TABLE)[
        "cache"
    ]

    assert cache["music"]["_dirname"] == "music"
    assert cache["music"]["town"] == "Town.mid"
    assert cache["music"]["戦闘1"] == "Battle 1.mid"


def test_game_files_win_over_the_rtp():
    cache = build_index(["Music/戦闘1.mid"], {"Music": ["Battle 1.mid"]}, RTP_TABLE)[
        "cache"
    ]

    assert cache["music"]["戦闘1"] == "戦闘1.mid"
    assert cache["music"]["battle1"] == "Battle 1.mid"


def test_rtp_files_outside_the_table_keep_their_own_name():
    cache = build_index([], {"ChipSet": ["retro_World.png"]}, RTP_TABLE)["cache"]

    assert cache["chipset"] == {"_dirname": "ChipSet", "retro_world": "retro_World.png"}


def test_reserved_dirname_file_is_skipped():
    cache = build_index(["Music/_dirname"], {}, {})["cache"]

    assert cache["music"] == {"_dirname": "Music"}


def _rtp_dir(tmp_path: Path) -> Path:
    for path in ("Music/Battle 1.mid", "System/System.png", "Music/.gitignore"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes(b"")
    return tmp_path


def test_rtp_files_are_listed_by_folder(tmp_path: Path):
    handler = EasyRpgHandler(rtp_path=str(_rtp_dir(tmp_path)))

    assert handler.rtp_files == {
        "Music": ["Battle 1.mid"],
        "System": ["System.png"],
    }


def test_missing_rtp_folder_lists_nothing(tmp_path: Path):
    handler = EasyRpgHandler(rtp_path=str(tmp_path / "missing"))

    assert handler.rtp_files == {}


def test_find_rtp_file_ignores_the_folder_case(tmp_path: Path):
    handler = EasyRpgHandler(rtp_path=str(_rtp_dir(tmp_path)))

    assert handler.find_rtp_file("music/Battle 1.mid") == "Music/Battle 1.mid"
    assert handler.find_rtp_file("Music/battle 1.mid") is None
    assert handler.find_rtp_file("Music/../System/System.png") is None


def test_is_game_needs_the_database_at_the_root():
    assert EasyRpgHandler.is_game(["RPG_RT.LDB", "Music/Town.mid"])
    assert not EasyRpgHandler.is_game(["Game/RPG_RT.ldb"])


def test_rtp_table_ships_with_the_handler():
    music = easyrpg_handler.rtp_table["music"]

    assert any(normalize_name("戦闘1") in row and "battle 1" in row for row in music)
