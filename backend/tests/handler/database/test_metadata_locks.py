from sqlalchemy import select
from tests.factories import make_rom

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.collection import VirtualCollectionRom
from models.platform import Platform
from models.rom import Rom, RomFacets


def _memberships(rom_id: int) -> list[tuple[str, str, str | None, str | None]]:
    with sync_session.begin() as session:
        return list(
            session.execute(
                select(
                    VirtualCollectionRom.type,
                    VirtualCollectionRom.name,
                    VirtualCollectionRom.path_cover_s,
                    VirtualCollectionRom.path_cover_l,
                )
                .where(VirtualCollectionRom.rom_id == rom_id)
                .order_by(VirtualCollectionRom.type, VirtualCollectionRom.name)
            ).tuples()
        )


def _names(rom_id: int) -> dict[str, set[str]]:
    memberships = _memberships(rom_id)
    return {
        type_: {name for row_type, name, _, _ in memberships if row_type == type_}
        for type_ in (
            "genre",
            "franchise",
            "collection",
            "company",
            "mode",
            "publisher",
            "developer",
        )
    }


def test_insert_applies_metadata_locks_to_facets_and_memberships(platform: Platform):
    rom = make_rom(
        platform,
        "insert with locks",
        manual_metadata={"genres": ["Generated"]},
        metadata_locks={
            "genres": ["Locked"],
            "cover": {
                "url": None,
                "small": "locked-small.png",
                "large": "locked-large.png",
            },
        },
    )

    with sync_session.begin() as session:
        facets = session.get_one(RomFacets, rom.id)
        assert facets.genres == ["Locked"]

    rows = _memberships(rom.id)
    assert rows == [("genre", "Locked", "locked-small.png", "locked-large.png")]


def test_cover_update_preserves_all_seven_unlocked_membership_types(
    platform: Platform,
):
    other_rom = make_rom(
        platform,
        "other memberships",
        manual_metadata={"genres": ["Other genre"], "publishers": ["Other publisher"]},
    )
    other_memberships_before = _memberships(other_rom.id)
    rom = make_rom(
        platform,
        "unlocked memberships",
        manual_metadata={
            "genres": ["Action"],
            "franchises": ["Series"],
            "collections": ["Set"],
            "companies": ["Studio"],
            "game_modes": ["Single-player"],
            "publishers": ["Publisher"],
            "developers": ["Developer"],
        },
    )

    db_rom_handler.update_rom(
        rom.id, {"path_cover_s": "small.png", "path_cover_l": "large.png"}
    )

    assert _names(rom.id) == {
        "genre": {"Action"},
        "franchise": {"Series"},
        "collection": {"Set"},
        "company": {"Studio"},
        "mode": {"Single-player"},
        "publisher": {"Publisher"},
        "developer": {"Developer"},
    }
    assert all(
        (small, large) == ("small.png", "large.png")
        for _, _, small, large in _memberships(rom.id)
    )
    assert _memberships(other_rom.id) == other_memberships_before


def test_publisher_and_developer_changes_reapply_other_active_locks(
    platform: Platform,
):
    provider = {
        "genres": ["Generated genre"],
        "franchises": ["Series"],
        "collections": ["Set"],
        "companies": ["Studio"],
        "game_modes": ["Single-player"],
        "publishers": ["Publisher A"],
        "developers": ["Developer A"],
    }
    rom = make_rom(
        platform,
        "locked memberships",
        manual_metadata=provider,
        path_cover_s="source-small.png",
        path_cover_l="source-large.png",
    )
    locks = {
        "genres": ["Locked genre"],
        "cover": {
            "url": None,
            "small": "locked-small.png",
            "large": "locked-large.png",
        },
    }
    db_rom_handler.update_rom(rom.id, {"metadata_locks": locks})

    provider["publishers"] = ["Publisher B"]
    db_rom_handler.update_rom(rom.id, {"manual_metadata": dict(provider)})
    provider["developers"] = ["Developer B"]
    db_rom_handler.update_rom(rom.id, {"manual_metadata": dict(provider)})

    assert _names(rom.id) == {
        "genre": {"Locked genre"},
        "franchise": {"Series"},
        "collection": {"Set"},
        "company": {"Studio"},
        "mode": {"Single-player"},
        "publisher": {"Publisher B"},
        "developer": {"Developer B"},
    }
    assert all(
        (small, large) == ("locked-small.png", "locked-large.png")
        for _, _, small, large in _memberships(rom.id)
    )

    with sync_session.begin() as session:
        current = session.get_one(Rom, rom.id)
        assert current.metadata_locks == locks
        assert current.manual_metadata == provider


def test_empty_array_lock_does_not_fall_back_to_generated_membership(
    platform: Platform,
):
    rom = make_rom(
        platform,
        "empty genre lock",
        manual_metadata={"genres": ["Generated"]},
    )
    db_rom_handler.update_rom(rom.id, {"metadata_locks": {"genres": []}})

    assert _names(rom.id)["genre"] == set()


def test_cover_json_null_is_stored_as_sql_null_in_memberships(platform: Platform):
    rom = make_rom(
        platform,
        "null cover lock",
        manual_metadata={"genres": ["Action"]},
        path_cover_s="source-small.png",
        path_cover_l="source-large.png",
    )
    db_rom_handler.update_rom(
        rom.id,
        {"metadata_locks": {"cover": {"url": None, "small": None, "large": None}}},
    )

    rows = _memberships(rom.id)
    assert rows == [("genre", "Action", None, None)]


def test_unlock_rebuilds_from_latest_generated_values(platform: Platform):
    rom = make_rom(
        platform,
        "unlock membership",
        manual_metadata={"genres": ["Generated A"]},
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "metadata_locks": {
                "genres": ["Locked"],
                "cover": {"small": "locked-small.png", "large": "locked-large.png"},
            }
        },
    )
    db_rom_handler.update_rom(rom.id, {"manual_metadata": {"genres": ["Generated B"]}})
    db_rom_handler.update_rom(
        rom.id,
        {
            "metadata_locks": {
                "cover": {"small": "locked-small.png", "large": "locked-large.png"}
            }
        },
    )

    assert _names(rom.id)["genre"] == {"Generated B"}
    assert all(
        (small, large) == ("locked-small.png", "locked-large.png")
        for _, _, small, large in _memberships(rom.id)
    )

    db_rom_handler.update_rom(rom.id, {"metadata_locks": {}})
    assert _names(rom.id)["genre"] == {"Generated B"}
