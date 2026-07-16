from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from config import ROMM_DB_DRIVER
from handler.auth import auth_handler
from handler.database import (
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from handler.database.roms_handler import _postgresql_trgm_available
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom, compute_name_sort_key
from models.user import Role, User


def test_platforms():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    db_platform_handler.add_platform(platform)

    platforms = db_platform_handler.get_platforms()
    assert len(platforms) == 1

    platform = db_platform_handler.get_platform_by_fs_slug(platform.fs_slug)
    assert platform is not None
    assert platform.name == "test_platform"

    db_platform_handler.mark_missing_platforms([])
    platforms = db_platform_handler.get_platforms()
    assert len(platforms) == 1


def test_roms(rom: Rom, platform: Platform):
    db_rom_handler.add_rom(
        Rom(
            platform_id=rom.platform_id,
            name="test_rom_2",
            slug="test_rom_slug_2",
            fs_name="test_rom_2",
            fs_name_no_tags="test_rom_2",
            fs_name_no_ext="test_rom_2",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )

    roms = db_rom_handler.get_roms_scalar(platform_ids=[platform.id])
    assert len(roms) == 2

    rom_1 = db_rom_handler.get_rom(roms[0].id)
    assert rom_1 is not None
    assert rom_1.fs_name == "test_rom.zip"

    db_rom_handler.update_rom(roms[1].id, {"fs_name": "test_rom_2_updated"})
    rom_2 = db_rom_handler.get_rom(roms[1].id)
    assert rom_2 is not None
    assert rom_2.fs_name == "test_rom_2_updated"

    db_rom_handler.delete_rom(rom.id)

    roms = db_rom_handler.get_roms_scalar(platform_ids=[platform.id])
    assert len(roms) == 1

    db_rom_handler.mark_missing_roms(rom_2.platform_id, [])

    roms = db_rom_handler.get_roms_scalar(platform_ids=[platform.id])
    assert len(roms) == 1


def test_multi_file_rom_backref_survives_session_close(multi_file_rom: Rom):
    """Multi-file ROM downloads read `file.rom.full_path` after the handler
    session closes. The detail loaders eager-load `Rom.files` but not the
    reverse `RomFile.rom` relationship, so without the backref being populated
    this raises `DetachedInstanceError` (a 500 on the download endpoint).
    """
    folder_path = f"{multi_file_rom.fs_path}/{multi_file_rom.fs_name}"

    # `multi_file_rom` is returned by `get_rom`, with the session already closed.
    assert len(multi_file_rom.files) == 2
    for file in multi_file_rom.files:
        # All of these dereference `file.rom` on a now-detached instance.
        assert file.rom.full_path == folder_path
        assert file.is_top_level
        assert file.file_name_for_download() == file.file_name

    # `get_roms_by_ids` (used by the bulk zip download) must behave the same.
    by_ids = db_rom_handler.get_roms_by_ids([multi_file_rom.id])
    assert len(by_ids) == 1
    for file in by_ids[0].files:
        assert file.rom.full_path == folder_path


def test_rom_files_for_rom_id_loads_backref(multi_file_rom: Rom):
    """The scan/metadata-matching fallback fetches a ROM's files on demand and
    reads `RomFile.is_top_level` -> `RomFile.rom.full_path`. The backref must be
    eager-loaded so it survives the handler session closing.
    """
    folder_path = f"{multi_file_rom.fs_path}/{multi_file_rom.fs_name}"

    files = db_rom_handler.rom_files_for_rom_id(multi_file_rom.id)
    assert len(files) == 2
    for file in files:
        # Both dereference `file.rom` on a now-detached instance.
        assert file.rom.full_path == folder_path
        assert file.is_top_level


def test_filter_last_played(rom: Rom, platform: Platform, admin_user: User):
    second_rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="test_rom_unplayed",
            slug="test_rom_unplayed_slug",
            fs_name="test_rom_unplayed.zip",
            fs_name_no_tags="test_rom_unplayed",
            fs_name_no_ext="test_rom_unplayed",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=second_rom.id, user_id=admin_user.id)

    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None

    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    )

    played_roms = db_rom_handler.get_roms_scalar(
        user_id=admin_user.id, last_played=True
    )
    assert {r.id for r in played_roms} == {rom.id}

    unplayed_roms = db_rom_handler.get_roms_scalar(
        user_id=admin_user.id, last_played=False
    )
    assert {r.id for r in unplayed_roms} == {second_rom.id}


def test_filter_by_search_term_with_multiple_terms(platform: Platform):
    rom_wwe = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="WWE SmackDown! Here Comes the Pain",
            slug="wwe-smackdown-here-comes-the-pain",
            fs_name="WWE_SmackDown_Here_Comes_the_Pain.zip",
            fs_name_no_tags="WWE_SmackDown_Here_Comes_the_Pain",
            fs_name_no_ext="WWE_SmackDown_Here_Comes_the_Pain",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom_wcw = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="WCW Nitro",
            slug="wcw-nitro",
            fs_name="WCW_Nitro.zip",
            fs_name_no_tags="WCW_Nitro",
            fs_name_no_ext="WCW_Nitro",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom_tna = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="TNA Impact!",
            slug="tna-impact",
            fs_name="TNA_Impact.zip",
            fs_name_no_tags="TNA_Impact",
            fs_name_no_ext="TNA_Impact",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    _rom_non_matching = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Super Mario World",
            slug="super-mario-world",
            fs_name="Super_Mario_World.zip",
            fs_name_no_tags="Super_Mario_World",
            fs_name_no_ext="Super_Mario_World",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )

    # Test with multiple search terms
    search_term = "WWE|WCW|TNA|wrestling"
    filtered_roms = db_rom_handler.get_roms_scalar(search_term=search_term)

    expected_rom_ids = {rom_wwe.id, rom_wcw.id, rom_tna.id}
    actual_rom_ids = {r.id for r in filtered_roms}
    assert actual_rom_ids == expected_rom_ids

    # Test with a term that doesn't match anything
    search_term_no_match = "nonexistent"
    filtered_roms_no_match = db_rom_handler.get_roms_scalar(
        search_term=search_term_no_match
    )
    assert len(filtered_roms_no_match) == 0

    # Test with a single search term
    search_term_single = "WWE"
    filtered_roms_single = db_rom_handler.get_roms_scalar(
        search_term=search_term_single
    )
    expected_rom_ids_single = {rom_wwe.id}
    actual_rom_ids_single = {r.id for r in filtered_roms_single}
    assert actual_rom_ids_single == expected_rom_ids_single


def test_filter_by_search_term_multi_word_and_ranking(platform: Platform):
    def _add(name: str) -> Rom:
        fs = name.replace(" ", "_")
        return db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=name,
                slug=name.lower().replace(" ", "-"),
                fs_name=f"{fs}.zip",
                fs_name_no_tags=fs,
                fs_name_no_ext=fs,
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )

    ff = _add("Final Fantasy")
    ff7 = _add("Final Fantasy VII")
    fantasy_final = _add("Fantasy Final")  # both words, reversed order
    _add("Final Combat")  # only "final"
    _add("Angelique - Voice Fantasy")  # only "fantasy"
    _add("Super Mario World")  # neither word

    results = db_rom_handler.get_roms_scalar(search_term="final fantasy")
    result_ids = [r.id for r in results]

    # Only titles containing BOTH words appear (AND semantics).
    assert set(result_ids) == {ff.id, ff7.id, fantasy_final.id}

    # Relevance ordering is engine-specific: MySQL/MariaDB rank with
    # MATCH ... AGAINST, PostgreSQL ranks with pg_trgm similarity() (when the
    # extension is installed), and each has its own tie-breaking behavior.
    if ROMM_DB_DRIVER in ("mariadb", "mysql"):
        # Exact-order phrase matches rank above the reversed-order match.
        assert result_ids.index(ff.id) < result_ids.index(fantasy_final.id)
        assert result_ids.index(ff7.id) < result_ids.index(fantasy_final.id)
    elif ROMM_DB_DRIVER == "postgresql" and _postgresql_trgm_available():
        # "Final Fantasy" and "Fantasy Final" share the same trigram set as the
        # query, so both are maximally similar; "Final Fantasy VII" carries the
        # extra "VII" trigrams, lowering its similarity, so it ranks last.
        assert result_ids.index(ff7.id) > result_ids.index(ff.id)
        assert result_ids.index(ff7.id) > result_ids.index(fantasy_final.id)

    # The relevance ORDER BY must also survive the group_by_meta_id subquery
    # wrapping used by the gallery (each ROM here is its own group).
    grouped = db_rom_handler.get_roms_scalar(
        search_term="final fantasy", group_by_meta_id=True
    )
    assert {r.id for r in grouped} == {ff.id, ff7.id, fantasy_final.id}

    # An explicit sort takes priority over relevance: ordering by name asc puts
    # "Fantasy Final" first (relevance is only the tiebreaker here).
    explicit = db_rom_handler.get_roms_scalar(
        search_term="final fantasy", order_by="name", order_dir="asc"
    )
    explicit_ids = [r.id for r in explicit]
    assert explicit_ids.index(fantasy_final.id) < explicit_ids.index(ff.id)


def test_sibling_roms_empty_fs_name_no_tags_not_matched(platform: Platform):
    """ROMs with empty fs_name_no_tags should NOT be matched as siblings.

    Japanese ROMs often have names starting with region tags (e.g., "(Japan) Sonic Jam.iso"),
    which results in an empty fs_name_no_tags. Without a guard, all such ROMs on the same
    platform would incorrectly be matched as siblings of each other.
    """
    rom1 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="(Japan) Game A",
            slug="japan-game-a",
            fs_name="(Japan) Game A.iso",
            fs_name_no_tags="",  # Empty due to leading region tag
            fs_name_no_ext="(Japan) Game A",
            fs_extension="iso",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom2 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="(Japan) Game B",
            slug="japan-game-b",
            fs_name="(Japan) Game B.iso",
            fs_name_no_tags="",  # Empty due to leading region tag
            fs_name_no_ext="(Japan) Game B",
            fs_extension="iso",
            fs_path=f"{platform.slug}/roms",
        )
    )

    loaded_rom1 = db_rom_handler.get_rom(rom1.id)
    loaded_rom2 = db_rom_handler.get_rom(rom2.id)
    assert loaded_rom1 is not None
    assert loaded_rom2 is not None

    # ROMs with empty fs_name_no_tags should NOT be siblings of each other
    sibling_ids1 = {s.id for s in loaded_rom1.sibling_roms}
    sibling_ids2 = {s.id for s in loaded_rom2.sibling_roms}
    assert rom2.id not in sibling_ids1
    assert rom1.id not in sibling_ids2


def test_sibling_roms_fs_name_no_tags_not_matched(platform: Platform):
    """ROMs with matching fs_name_no_tags but no shared metadata ID should NOT
    be matched as siblings. Sibling matching is based only on metadata IDs.
    """
    rom1 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Sonic Jam (USA)",
            slug="sonic-jam-usa",
            fs_name="Sonic Jam (USA).iso",
            fs_name_no_tags="Sonic Jam",
            fs_name_no_ext="Sonic Jam (USA)",
            fs_extension="iso",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom2 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Sonic Jam (Japan)",
            slug="sonic-jam-japan",
            fs_name="Sonic Jam (Japan).iso",
            fs_name_no_tags="Sonic Jam",
            fs_name_no_ext="Sonic Jam (Japan)",
            fs_extension="iso",
            fs_path=f"{platform.slug}/roms",
        )
    )

    loaded_rom1 = db_rom_handler.get_rom(rom1.id)
    loaded_rom2 = db_rom_handler.get_rom(rom2.id)
    assert loaded_rom1 is not None
    assert loaded_rom2 is not None

    # ROMs with same fs_name_no_tags but no metadata IDs should NOT be siblings
    sibling_ids1 = {s.id for s in loaded_rom1.sibling_roms}
    sibling_ids2 = {s.id for s in loaded_rom2.sibling_roms}
    assert rom2.id not in sibling_ids1
    assert rom1.id not in sibling_ids2


def test_group_by_meta_id_with_empty_fs_name_no_tags(platform: Platform):
    """ROMs with no metadata IDs should each get their own group when using
    group_by_meta_id, not be grouped into a single catch-all group.
    """
    rom_names = ["(Japan) Game A", "(Japan) Game B", "(Japan) Game C"]
    for name in rom_names:
        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=name,
                slug=name.lower().replace(" ", "-").replace("(", "").replace(")", ""),
                fs_name=f"{name}.iso",
                fs_name_no_tags="",  # Empty due to leading region tag
                fs_name_no_ext=name,
                fs_extension="iso",
                fs_path=f"{platform.slug}/roms",
            )
        )

    roms = db_rom_handler.get_roms_scalar(
        platform_ids=[platform.id],
        order_by="name",
        order_dir="asc",
        group_by_meta_id=True,
    )
    # All 3 ROMs should be shown, not collapsed into 1
    assert len(roms) == len(rom_names)


def test_natural_sort_order(platform: Platform):
    """Numbers in names should sort numerically, not lexicographically."""
    for name in ["Game 10", "Game 2", "Game 1"]:
        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=name,
                slug=name.lower().replace(" ", "-"),
                fs_name=f"{name}.zip",
                fs_name_no_tags=name,
                fs_name_no_ext=name,
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )

    roms = db_rom_handler.get_roms_scalar(
        platform_ids=[platform.id], order_by="name", order_dir="asc"
    )
    assert [r.name for r in roms] == ["Game 1", "Game 2", "Game 10"]


def test_article_stripping_sort(platform: Platform):
    """Leading articles (the, a, an) are stripped when sorting, case-insensitively."""
    for name in ["Zelda", "The Legend", "A Quest"]:
        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=name,
                slug=name.lower().replace(" ", "-"),
                fs_name=f"{name}.zip",
                fs_name_no_tags=name,
                fs_name_no_ext=name,
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )

    roms = db_rom_handler.get_roms_scalar(
        platform_ids=[platform.id], order_by="name", order_dir="asc"
    )
    # "The Legend" → sorts as "legend", "A Quest" → "quest", "Zelda" → "zelda"
    assert [r.name for r in roms] == ["The Legend", "A Quest", "Zelda"]


def test_custom_name_sort_key_overrides_name_sort_order(platform: Platform):
    for name, sort_override in [
        ("Display Z", "Alpha"),
        ("Display M", None),
        ("Display A", "Zulu"),
    ]:
        rom = Rom(
            platform_id=platform.id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
        # A custom key pins ordering; without one it derives from `name`.
        if sort_override is not None:
            rom.name_sort_key = compute_name_sort_key(sort_override)
        db_rom_handler.add_rom(rom)

    roms = db_rom_handler.get_roms_scalar(
        platform_ids=[platform.id], order_by="name", order_dir="asc"
    )
    assert [r.name for r in roms] == ["Display Z", "Display M", "Display A"]


def test_bulk_mark_present(platform: Platform):
    """bulk_mark_present sets missing_from_fs=False for the given ROM IDs."""
    roms = []
    for i in range(5):
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=f"rom_{i}",
                slug=f"rom-{i}",
                fs_name=f"rom_{i}.zip",
                fs_name_no_tags=f"rom_{i}",
                fs_name_no_ext=f"rom_{i}",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
                missing_from_fs=True,
            )
        )
        roms.append(rom)

    # Mark first 3 as present
    db_rom_handler.bulk_mark_present(platform.id, [r.id for r in roms[:3]])

    for r in roms[:3]:
        updated = db_rom_handler.get_rom(r.id)
        assert updated is not None
        assert updated.missing_from_fs is False

    for r in roms[3:]:
        updated = db_rom_handler.get_rom(r.id)
        assert updated is not None
        assert updated.missing_from_fs is True


def test_bulk_mark_present_empty_list(platform: Platform):
    """bulk_mark_present with an empty list is a no-op."""
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_lonely",
            slug="rom-lonely",
            fs_name="rom_lonely.zip",
            fs_name_no_tags="rom_lonely",
            fs_name_no_ext="rom_lonely",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            missing_from_fs=True,
        )
    )

    db_rom_handler.bulk_mark_present(platform.id, [])

    updated = db_rom_handler.get_rom(rom.id)
    assert updated is not None
    assert updated.missing_from_fs is True


def test_bulk_mark_present_chunking(platform: Platform):
    """bulk_mark_present handles >1000 IDs via internal chunking."""
    roms = []
    for i in range(1050):
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=f"rom_{i}",
                slug=f"rom-{i}",
                fs_name=f"rom_{i}.zip",
                fs_name_no_tags=f"rom_{i}",
                fs_name_no_ext=f"rom_{i}",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
                missing_from_fs=True,
            )
        )
        roms.append(rom)

    all_ids = [r.id for r in roms]
    db_rom_handler.bulk_mark_present(platform.id, all_ids)

    # Spot-check a few across chunk boundaries
    for idx in [0, 999, 1000, 1049]:
        updated = db_rom_handler.get_rom(roms[idx].id)
        assert updated is not None
        assert updated.missing_from_fs is False


def test_mark_missing_roms_small_platform(platform: Platform):
    """mark_missing_roms correctly identifies missing ROMs with a small keep list."""
    rom_a = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_a",
            slug="rom-a",
            fs_name="rom_a.zip",
            fs_name_no_tags="rom_a",
            fs_name_no_ext="rom_a",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom_b = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_b",
            slug="rom-b",
            fs_name="rom_b.zip",
            fs_name_no_tags="rom_b",
            fs_name_no_ext="rom_b",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_c",
            slug="rom-c",
            fs_name="rom_c.zip",
            fs_name_no_tags="rom_c",
            fs_name_no_ext="rom_c",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )

    # Keep only rom_a and rom_c
    missing = db_rom_handler.mark_missing_roms(platform.id, ["rom_a.zip", "rom_c.zip"])

    assert len(missing) == 1
    assert missing[0].fs_name == "rom_b.zip"

    updated_b = db_rom_handler.get_rom(rom_b.id)
    assert updated_b is not None
    assert updated_b.missing_from_fs is True

    updated_a = db_rom_handler.get_rom(rom_a.id)
    assert updated_a is not None
    assert updated_a.missing_from_fs is False


def test_mark_missing_roms_large_platform(platform: Platform):
    """mark_missing_roms correctly identifies missing ROMs with a large keep list."""
    rom_present = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_present",
            slug="rom-present",
            fs_name="rom_present.zip",
            fs_name_no_tags="rom_present",
            fs_name_no_ext="rom_present",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom_missing = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="rom_missing",
            slug="rom-missing",
            fs_name="rom_missing.zip",
            fs_name_no_tags="rom_missing",
            fs_name_no_ext="rom_missing",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )

    # Build a large keep list to verify mark_missing_roms() handles many entries.
    # Only rom_present.zip actually exists in DB; the rest are just filler.
    fs_roms_to_keep = ["rom_present.zip"] + [f"filler_{i}.zip" for i in range(501)]

    missing = db_rom_handler.mark_missing_roms(platform.id, fs_roms_to_keep)

    assert len(missing) == 1
    assert missing[0].fs_name == "rom_missing.zip"

    updated_present = db_rom_handler.get_rom(rom_present.id)
    assert updated_present is not None
    assert updated_present.missing_from_fs is False

    updated_missing = db_rom_handler.get_rom(rom_missing.id)
    assert updated_missing is not None
    assert updated_missing.missing_from_fs is True


def test_mark_missing_roms_large_platform_all_present(platform: Platform):
    """When all ROMs are in the keep list, none should be marked missing."""
    roms = []
    for i in range(3):
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=f"rom_{i}",
                slug=f"rom-{i}",
                fs_name=f"rom_{i}.zip",
                fs_name_no_tags=f"rom_{i}",
                fs_name_no_ext=f"rom_{i}",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )
        roms.append(rom)

    # Keep list has all real ROMs plus filler to exceed 500
    fs_roms_to_keep = [f"rom_{i}.zip" for i in range(3)] + [
        f"filler_{i}.zip" for i in range(500)
    ]

    missing = db_rom_handler.mark_missing_roms(platform.id, fs_roms_to_keep)
    assert len(missing) == 0

    for rom in roms:
        updated = db_rom_handler.get_rom(rom.id)
        assert updated is not None
        assert updated.missing_from_fs is False


def test_mark_missing_roms_large_platform_all_missing(platform: Platform):
    """When no ROMs are in the keep list, all should be marked missing."""
    roms = []
    for i in range(3):
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=f"rom_{i}",
                slug=f"rom-{i}",
                fs_name=f"rom_{i}.zip",
                fs_name_no_tags=f"rom_{i}",
                fs_name_no_ext=f"rom_{i}",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )
        roms.append(rom)

    # Keep list has only filler (none of the real ROMs)
    fs_roms_to_keep = [f"filler_{i}.zip" for i in range(501)]

    missing = db_rom_handler.mark_missing_roms(platform.id, fs_roms_to_keep)
    assert len(missing) == 3

    missing_names = {r.fs_name for r in missing}
    assert missing_names == {"rom_0.zip", "rom_1.zip", "rom_2.zip"}


def test_mark_missing_roms_does_not_affect_other_platforms(platform: Platform):
    """mark_missing_roms should only affect ROMs on the target platform."""
    other_platform = db_platform_handler.add_platform(
        Platform(
            name="other_platform",
            slug="other_platform_slug",
            fs_slug="other_platform_slug",
        )
    )

    db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="target_rom",
            slug="target-rom",
            fs_name="target_rom.zip",
            fs_name_no_tags="target_rom",
            fs_name_no_ext="target_rom",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    rom_on_other = db_rom_handler.add_rom(
        Rom(
            platform_id=other_platform.id,
            name="other_rom",
            slug="other-rom",
            fs_name="other_rom.zip",
            fs_name_no_tags="other_rom",
            fs_name_no_ext="other_rom",
            fs_extension="zip",
            fs_path=f"{other_platform.slug}/roms",
        )
    )

    # Use flip-based path (>500 items), keeping nothing on target platform
    fs_roms_to_keep = [f"filler_{i}.zip" for i in range(501)]
    missing = db_rom_handler.mark_missing_roms(platform.id, fs_roms_to_keep)

    assert len(missing) == 1
    assert missing[0].fs_name == "target_rom.zip"

    # Other platform's ROM should be untouched
    updated_other = db_rom_handler.get_rom(rom_on_other.id)
    assert updated_other is not None
    assert updated_other.missing_from_fs is False


def test_users(admin_user):
    db_user_handler.add_user(
        User(
            username="new_user",
            hashed_password=auth_handler.get_password_hash("new_password"),
        )
    )

    all_users = db_user_handler.get_users()
    assert len(all_users) == 2

    new_user = db_user_handler.get_user_by_username("new_user")
    assert new_user is not None
    assert new_user.username == "new_user"
    assert new_user.role == Role.USER
    assert new_user.enabled

    db_user_handler.update_user(new_user.id, {"role": Role.ADMIN})

    new_user = db_user_handler.get_user(new_user.id)
    assert new_user is not None
    assert new_user.role == Role.ADMIN

    db_user_handler.delete_user(new_user.id)

    all_users = db_user_handler.get_users()
    assert len(all_users) == 1

    with pytest.raises(IntegrityError):
        db_user_handler.add_user(
            User(
                username="test_admin",
                hashed_password=auth_handler.get_password_hash("new_password"),
                role=Role.ADMIN,
            )
        )


def test_saves(save: Save, platform: Platform, admin_user: User):
    db_save_handler.add_save(
        Save(
            rom_id=save.rom_id,
            user_id=admin_user.id,
            file_name="test_save_2.sav",
            file_name_no_tags="test_save_2",
            file_name_no_ext="test_save_2",
            file_extension="sav",
            emulator="test_emulator",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=1.0,
        )
    )

    rom = db_rom_handler.get_rom(save.rom_id)
    assert rom is not None
    assert len(rom.saves) == 2

    new_save = db_save_handler.get_save(user_id=admin_user.id, id=rom.saves[0].id)
    assert new_save is not None
    assert new_save.file_name == "test_save.sav"

    db_save_handler.update_save(new_save.id, {"file_name": "test_save_2.sav"})
    new_save = db_save_handler.get_save(user_id=admin_user.id, id=new_save.id)
    assert new_save is not None
    assert new_save.file_name == "test_save_2.sav"

    db_save_handler.delete_save(new_save.id)

    rom = db_rom_handler.get_rom(save.rom_id)
    assert rom is not None
    assert len(rom.saves) == 1


def test_states(state: State, platform: Platform, admin_user: User):
    db_state_handler.add_state(
        State(
            rom_id=state.rom_id,
            user_id=admin_user.id,
            file_name="test_state_2.state",
            file_name_no_tags="test_state_2",
            file_name_no_ext="test_state_2",
            file_extension="state",
            file_path=f"{platform.slug}/states",
            file_size_bytes=1.0,
        )
    )

    rom = db_rom_handler.get_rom(id=state.rom_id)
    assert rom is not None
    assert len(rom.states) == 2

    new_state = db_state_handler.get_state(user_id=admin_user.id, id=rom.states[0].id)
    assert new_state is not None
    assert new_state.file_name == "test_state.state"

    db_state_handler.update_state(new_state.id, {"file_name": "test_state_2.state"})
    new_state = db_state_handler.get_state(user_id=admin_user.id, id=new_state.id)
    assert new_state is not None
    assert new_state.file_name == "test_state_2.state"

    db_state_handler.delete_state(id=new_state.id)

    rom = db_rom_handler.get_rom(id=state.rom_id)
    assert rom is not None
    assert len(rom.states) == 1


def test_screenshots(screenshot: Screenshot, platform: Platform, admin_user: User):
    db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=screenshot.rom_id,
            user_id=admin_user.id,
            file_name="test_screenshot_2.png",
            file_name_no_tags="test_screenshot_2",
            file_name_no_ext="test_screenshot_2",
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=1.0,
        )
    )

    rom = db_rom_handler.get_rom(screenshot.rom_id)
    assert rom is not None
    assert len(rom.screenshots) == 2

    new_screenshot = db_screenshot_handler.get_screenshot_by_id(
        id=rom.screenshots[0].id
    )
    assert new_screenshot is not None
    assert new_screenshot.file_name == "test_screenshot.png"

    db_screenshot_handler.update_screenshot(
        new_screenshot.id, {"file_name": "test_screenshot_2.png"}
    )
    new_screenshot = db_screenshot_handler.get_screenshot_by_id(id=new_screenshot.id)
    assert new_screenshot is not None
    assert new_screenshot.file_name == "test_screenshot_2.png"

    db_screenshot_handler.delete_screenshot(id=new_screenshot.id)

    rom = db_rom_handler.get_rom(id=screenshot.rom_id)
    assert rom is not None
    assert len(rom.screenshots) == 1


def _add_rom_with_providers(platform: Platform, slug: str, **provider_ids) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=slug,
            slug=slug,
            fs_name=f"{slug}.zip",
            fs_name_no_tags=slug,
            fs_name_no_ext=slug,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            **provider_ids,
        )
    )


def test_filter_by_metadata_providers(rom: Rom, platform: Platform):
    # `rom` fixture has no provider ids (unmatched).
    rom_igdb = _add_rom_with_providers(platform, "rom_igdb", igdb_id=1)
    rom_moby = _add_rom_with_providers(platform, "rom_moby", moby_id=2)
    rom_both = _add_rom_with_providers(platform, "rom_both", igdb_id=3, moby_id=4)

    # "any" (OR): matched to at least one of the selected providers.
    any_igdb = db_rom_handler.get_roms_scalar(metadata_providers=["igdb"])
    assert {r.id for r in any_igdb} == {rom_igdb.id, rom_both.id}

    any_either = db_rom_handler.get_roms_scalar(
        metadata_providers=["igdb", "moby"], metadata_providers_logic="any"
    )
    assert {r.id for r in any_either} == {rom_igdb.id, rom_moby.id, rom_both.id}

    # "all" (AND): matched to every selected provider.
    all_both = db_rom_handler.get_roms_scalar(
        metadata_providers=["igdb", "moby"], metadata_providers_logic="all"
    )
    assert {r.id for r in all_both} == {rom_both.id}

    # "none" (NOT): matched to none of the selected providers.
    none_igdb = db_rom_handler.get_roms_scalar(
        metadata_providers=["igdb"], metadata_providers_logic="none"
    )
    assert {r.id for r in none_igdb} == {rom.id, rom_moby.id}


def test_filter_by_metadata_providers_unknown_value_is_ignored(
    rom: Rom, platform: Platform
):
    """Unknown provider slugs are dropped so the filter is a no-op rather than
    raising, keeping a stale bookmark or hand-edited URL from 500-ing."""
    rom_igdb = _add_rom_with_providers(platform, "rom_igdb", igdb_id=1)

    only_unknown = db_rom_handler.get_roms_scalar(metadata_providers=["bogus"])
    assert {r.id for r in only_unknown} == {rom.id, rom_igdb.id}

    known_and_unknown = db_rom_handler.get_roms_scalar(
        metadata_providers=["igdb", "bogus"]
    )
    assert {r.id for r in known_and_unknown} == {rom_igdb.id}


def _add_rom_with_tags(platform: Platform, slug: str, tags: list[str]) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=slug,
            slug=slug,
            fs_name=f"{slug}.zip",
            fs_name_no_tags=slug,
            fs_name_no_ext=slug,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            tags=tags,
        )
    )


def test_filter_by_tags(rom: Rom, platform: Platform):
    # `rom` fixture has no tags (untagged).
    rom_proto = _add_rom_with_tags(platform, "rom_proto", ["Proto"])
    rom_beta = _add_rom_with_tags(platform, "rom_beta", ["Beta"])
    rom_both = _add_rom_with_tags(platform, "rom_both", ["Proto", "Beta"])

    # "any" (OR): carries at least one of the selected tags.
    any_proto = db_rom_handler.get_roms_scalar(tags=["Proto"])
    assert {r.id for r in any_proto} == {rom_proto.id, rom_both.id}

    any_either = db_rom_handler.get_roms_scalar(
        tags=["Proto", "Beta"], tags_logic="any"
    )
    assert {r.id for r in any_either} == {rom_proto.id, rom_beta.id, rom_both.id}

    # "all" (AND): carries every selected tag.
    all_both = db_rom_handler.get_roms_scalar(tags=["Proto", "Beta"], tags_logic="all")
    assert {r.id for r in all_both} == {rom_both.id}

    # "none" (NOT): carries none of the selected tags.
    none_proto = db_rom_handler.get_roms_scalar(tags=["Proto"], tags_logic="none")
    assert {r.id for r in none_proto} == {rom.id, rom_beta.id}


def test_filter_by_tags_unknown_value_returns_no_matches(rom: Rom, platform: Platform):
    """A tag that no ROM carries simply matches nothing under "any" logic
    (free-form text match), rather than erroring."""
    _add_rom_with_tags(platform, "rom_proto", ["Proto"])

    only_unknown = db_rom_handler.get_roms_scalar(tags=["Nonexistent"])
    assert list(only_unknown) == []


def test_get_rom_filters_includes_tags(rom: Rom, platform: Platform):
    _add_rom_with_tags(platform, "rom_proto", ["Proto"])
    _add_rom_with_tags(platform, "rom_beta", ["Beta", "Demo"])

    filters = db_rom_handler.get_rom_filters()
    assert filters["tags"] == ["Beta", "Demo", "Proto"]
