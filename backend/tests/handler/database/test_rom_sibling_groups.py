from sqlalchemy import delete, select
from tests.factories import make_rom

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.platform import Platform
from models.rom import Rom, RomSiblingGroup, RomUser
from models.user import User


def _groups() -> dict[int, int]:
    with sync_session.begin() as session:
        return dict(
            session.execute(
                select(RomSiblingGroup.rom_id, RomSiblingGroup.group_id)
            ).all()
        )


def _siblings(rom: Rom) -> list[int]:
    loaded = db_rom_handler.get_rom(rom.id)
    assert loaded is not None
    return sorted(sibling.id for sibling in loaded.sibling_roms)


def _gallery(platform: Platform, user_id: int | None = None) -> list[int]:
    return [
        rom.id
        for rom in db_rom_handler.get_roms_scalar(
            platform_ids=[platform.id],
            order_by="name",
            order_dir="asc",
            group_by_meta_id=True,
            user_id=user_id,
        )
    ]


def _chain(platform: Platform) -> tuple[Rom, Rom, Rom]:
    """IGDB matched `first` and `bridge`, ScreenScraper `bridge` and `last`."""
    first = make_rom(platform, "Chain (USA)", igdb_id=10)
    bridge = make_rom(platform, "Chain (Europe)", igdb_id=10, ss_id=20)
    last = make_rom(platform, "Chain (Japan)", ss_id=20)
    return first, bridge, last


class TestSiblingGroups:
    def test_a_rom_with_no_sibling_has_no_group(self, platform: Platform):
        rom = make_rom(platform, "Alone", igdb_id=1)

        assert rom.id not in _groups()

    def test_a_chain_of_provider_ids_is_one_game(self, platform: Platform):
        first, bridge, last = _chain(platform)

        assert _groups() == {first.id: first.id, bridge.id: first.id, last.id: first.id}
        assert _siblings(first) == sorted([bridge.id, last.id])
        assert _siblings(last) == sorted([first.id, bridge.id])

    def test_a_partial_match_shares_the_card_of_a_full_one(self, platform: Platform):
        """The first non-null id differs (IGDB vs ScreenScraper), the game does not."""
        make_rom(platform, "Partial (USA)", igdb_id=30, ss_id=40)
        make_rom(platform, "Partial (Japan)", ss_id=40)

        assert len(_gallery(platform)) == 1

    def test_the_gallery_card_matches_the_game_page_siblings(self, platform: Platform):
        first, bridge, last = _chain(platform)

        (card,) = _gallery(platform)
        loaded = db_rom_handler.get_rom(card)
        assert loaded is not None
        assert sorted([card, *(s.id for s in loaded.sibling_roms)]) == sorted(
            [first.id, bridge.id, last.id]
        )

    def test_losing_the_bridging_id_splits_the_group(self, platform: Platform):
        first, bridge, last = _chain(platform)

        db_rom_handler.update_rom(bridge.id, {"ss_id": None})

        assert _groups() == {first.id: first.id, bridge.id: first.id}
        assert _siblings(last) == []

    def test_gaining_an_id_joins_two_groups(self, platform: Platform):
        usa = make_rom(platform, "Join (USA)", igdb_id=50)
        europe = make_rom(platform, "Join (Europe)", igdb_id=50)
        japan = make_rom(platform, "Join (Japan)", ss_id=60)
        korea = make_rom(platform, "Join (Korea)", ss_id=60)

        db_rom_handler.update_rom(europe.id, {"ss_id": 60})

        assert set(_groups().values()) == {usa.id}
        assert _siblings(korea) == sorted([usa.id, europe.id, japan.id])

    def test_moving_platform_leaves_the_group(
        self, platform: Platform, other_platform: Platform
    ):
        first, bridge, last = _chain(platform)

        db_rom_handler.update_rom(bridge.id, {"platform_id": other_platform.id})

        assert _groups() == {}
        assert _siblings(first) == []

    def test_deleting_the_bridge_splits_the_rest(self, platform: Platform):
        first, bridge, last = _chain(platform)

        db_rom_handler.delete_rom(bridge.id)

        assert _groups() == {}
        assert sorted(_gallery(platform)) == sorted([first.id, last.id])

    def test_rebuild_repairs_a_stale_group(self, platform: Platform):
        first, bridge, last = _chain(platform)
        with sync_session.begin() as session:
            session.execute(
                delete(RomSiblingGroup).where(RomSiblingGroup.rom_id == last.id)
            )
            session.add(RomSiblingGroup(rom_id=last.id, group_id=last.id))

        db_rom_handler.rebuild_sibling_groups()

        assert _groups() == {first.id: first.id, bridge.id: first.id, last.id: first.id}


class TestSiblingRepresentatives:
    def test_every_version_maps_to_the_gallery_card(
        self, admin_user: User, platform: Platform
    ):
        first, bridge, last = _chain(platform)
        (card,) = _gallery(platform, admin_user.id)

        representatives = db_rom_handler.get_sibling_representatives(
            [first.id, bridge.id, last.id], user_id=admin_user.id
        )

        assert representatives == {first.id: card, bridge.id: card, last.id: card}

    def test_the_users_main_version_wins(self, admin_user: User, platform: Platform):
        first, bridge, last = _chain(platform)
        rom_user = db_rom_handler.add_rom_user(rom_id=last.id, user_id=admin_user.id)
        db_rom_handler.update_rom_user(rom_user.id, {"is_main_sibling": True})

        representatives = db_rom_handler.get_sibling_representatives(
            [first.id], user_id=admin_user.id
        )

        assert representatives == {first.id: last.id}
        assert _gallery(platform, admin_user.id) == [last.id]

    def test_a_version_the_user_hid_does_not_represent(
        self, admin_user: User, platform: Platform
    ):
        first, bridge, last = _chain(platform)
        with sync_session.begin() as session:
            session.add(RomUser(rom_id=first.id, user_id=admin_user.id, hidden=True))

        representatives = db_rom_handler.get_sibling_representatives(
            [first.id], user_id=admin_user.id
        )

        assert representatives[first.id] != first.id

    def test_a_full_tie_goes_to_the_lowest_id(
        self, admin_user: User, platform: Platform
    ):
        """Same stem, same (absent) region: only the id can break the tie."""
        first = make_rom(platform, "Tie", fs_extension="zip", igdb_id=80)
        second = make_rom(platform, "Tie", fs_extension="7z", igdb_id=80)

        assert _gallery(platform, admin_user.id) == [first.id]
        assert db_rom_handler.get_sibling_representatives(
            [second.id], user_id=admin_user.id
        ) == {second.id: first.id}

    def test_a_rom_without_siblings_represents_itself(
        self, admin_user: User, platform: Platform
    ):
        rom = make_rom(platform, "Solo", igdb_id=70)

        assert db_rom_handler.get_sibling_representatives(
            [rom.id], user_id=admin_user.id
        ) == {rom.id: rom.id}
