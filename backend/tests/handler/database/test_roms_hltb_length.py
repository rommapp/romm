"""Sorting and range-filtering the gallery by HowLongToBeat main-story time.

`generated_hltb_main_story` (migration 0128) materializes the seconds buried in
the `hltb_metadata` blob so the length sort walks an index and the range filter
composes into SQL. A rom with no HowLongToBeat time derives NULL, which is what
keeps it out of a filtered result.
"""

import pytest

from handler.database import db_collection_handler, db_rom_handler
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import Rom
from models.user import User

SHORT_SECONDS = 2 * 3600
MEDIUM_SECONDS = 10 * 3600
LONG_SECONDS = 40 * 3600


def _make_rom(platform: Platform, fs_name: str, **metadata) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=fs_name,
            slug=fs_name,
            fs_name=f"{fs_name}.zip",
            fs_name_no_tags=fs_name,
            fs_name_no_ext=fs_name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    if metadata:
        rom = db_rom_handler.update_rom(rom.id, metadata)
    return rom


def _filtered_names(**kwargs) -> set[str]:
    return {rom.name for rom in db_rom_handler.get_roms_scalar(**kwargs)}


@pytest.fixture
def length_roms(platform: Platform) -> None:
    _make_rom(platform, "short", hltb_metadata={"main_story": SHORT_SECONDS})
    _make_rom(platform, "medium", hltb_metadata={"main_story": MEDIUM_SECONDS})
    _make_rom(platform, "long", hltb_metadata={"main_story": LONG_SECONDS})
    _make_rom(platform, "unknown")


class TestGeneratedColumn:
    @pytest.mark.parametrize(
        ("metadata", "expected"),
        [
            ({"main_story": MEDIUM_SECONDS}, MEDIUM_SECONDS),
            ({"main_story": 0}, None),
            ({"main_story": None}, None),
            ({"main_story": "not a number"}, None),
            ({"main_plus_extra": MEDIUM_SECONDS}, None),
            ({}, None),
        ],
    )
    def test_derives_the_main_story_seconds(
        self, platform: Platform, metadata: dict, expected: int | None
    ):
        rom = _make_rom(platform, "derived", hltb_metadata=metadata)

        reloaded = db_rom_handler.get_rom(rom.id)
        assert reloaded is not None
        assert reloaded.generated_hltb_main_story == expected


class TestLengthSort:
    def test_orders_by_the_indexed_roms_column(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("handler.database.roms_handler.ROMM_DB_DRIVER", "mariadb")
        query, order_column = db_rom_handler.get_roms_query(order_by="hltb_main_story")

        assert (
            "ORDER BY roms.generated_hltb_main_story IS NULL, "
            "roms.generated_hltb_main_story ASC"
        ) in str(query)
        assert order_column is Rom.generated_hltb_main_story

    @pytest.mark.parametrize("order_dir", ["asc", "desc"])
    def test_breaks_ties_on_the_primary_key(self, order_dir: str):
        """Length ties are common (every rom without a HowLongToBeat time is
        NULL), and the gallery pages by offset, so the order has to be total."""
        query, _ = db_rom_handler.get_roms_query(
            order_by="hltb_main_story", order_dir=order_dir
        )

        assert str(query).endswith(f"roms.id {order_dir.upper()}")

    def test_paging_a_tie_block_neither_repeats_nor_drops_a_rom(
        self, platform: Platform
    ):
        for index in range(10):
            _make_rom(
                platform, f"tied-{index}", hltb_metadata={"main_story": MEDIUM_SECONDS}
            )

        paged: list[str] = []
        for offset in range(0, 10, 3):
            page = db_rom_handler.get_roms_scalar(order_by="hltb_main_story")[
                offset : offset + 3
            ]
            paged.extend(rom.name for rom in page)

        assert sorted(paged) == sorted(f"tied-{i}" for i in range(10))

    def test_ascending(self, length_roms: None):
        ordered = [
            rom.name
            for rom in db_rom_handler.get_roms_scalar(order_by="hltb_main_story")
        ]

        assert ordered == ["short", "medium", "long", "unknown"]

    def test_descending(self, length_roms: None):
        ordered = [
            rom.name
            for rom in db_rom_handler.get_roms_scalar(
                order_by="hltb_main_story", order_dir="desc"
            )
        ]

        assert ordered == ["long", "medium", "short", "unknown"]


class TestLengthFilter:
    def test_minimum_only(self, length_roms: None):
        assert _filtered_names(hltb_main_story_min=MEDIUM_SECONDS) == {
            "medium",
            "long",
        }

    def test_maximum_only(self, length_roms: None):
        assert _filtered_names(hltb_main_story_max=MEDIUM_SECONDS) == {
            "short",
            "medium",
        }

    def test_both_bounds(self, length_roms: None):
        assert _filtered_names(
            hltb_main_story_min=SHORT_SECONDS + 1,
            hltb_main_story_max=LONG_SECONDS - 1,
        ) == {"medium"}

    def test_unset_bounds_filter_nothing(self, length_roms: None):
        assert _filtered_names() == {"short", "medium", "long", "unknown"}

    def test_a_zero_minimum_still_hides_roms_without_a_length(self, length_roms: None):
        assert _filtered_names(hltb_main_story_min=0) == {"short", "medium", "long"}


class TestSmartCollectionCriteria:
    def test_saved_length_range_scopes_membership(
        self, length_roms: None, admin_user: User
    ):
        smart_collection = db_collection_handler.add_smart_collection(
            SmartCollection(
                name="Short games",
                description="",
                user_id=admin_user.id,
                is_public=False,
                filter_criteria={"hltb_main_story_max": MEDIUM_SECONDS},
            )
        )

        assert _filtered_names(
            smart_collection_id=smart_collection.id, user_id=admin_user.id
        ) == {"short", "medium"}
