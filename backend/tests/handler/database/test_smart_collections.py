"""Smart collection membership as a composed query rather than a stored list.

A smart collection is a saved filter, so serving a page of it must apply its
criteria to the ROM query instead of assembling the whole membership list in
memory and writing it back on every read (see #4029).
"""

from collections.abc import Sequence

from handler.database import db_collection_handler, db_rom_handler, db_save_handler
from models.assets import Save
from models.collection import Collection, SmartCollection
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _add_rom(
    platform: Platform,
    name: str,
    *,
    cover: str = "",
    manual_metadata: dict | None = None,
    regions: list[str] | None = None,
) -> Rom:
    slug = name.lower().replace(" ", "_")
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=slug,
            fs_name=f"{slug}.zip",
            fs_name_no_tags=slug,
            fs_name_no_ext=slug,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            manual_metadata=manual_metadata or {},
            regions=regions or [],
            path_cover_s=cover,
            path_cover_l=cover,
        )
    )


def _add_smart_collection(
    user: User, criteria: dict, *, name: str = "Smart", is_public: bool = False
) -> SmartCollection:
    return db_collection_handler.add_smart_collection(
        SmartCollection(
            name=name,
            description="",
            user_id=user.id,
            is_public=is_public,
            filter_criteria=criteria,
        )
    )


def _favorite(user: User, roms: Sequence[Rom]) -> Collection:
    collection = db_collection_handler.add_collection(
        Collection(
            name=f"Favorites {user.id}",
            description="",
            user_id=user.id,
            is_favorite=True,
        )
    )
    db_collection_handler.add_roms_to_collection(
        collection.id, [rom.id for rom in roms]
    )
    return collection


def test_filter_roms_by_smart_collection_applies_criteria(
    platform: Platform, admin_user: User
):
    matching = [
        _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]}),
        _add_rom(platform, "Rally Two", manual_metadata={"genres": ["Racing"]}),
    ]
    _add_rom(platform, "Puzzler", manual_metadata={"genres": ["Puzzle"]})

    smart_collection = _add_smart_collection(admin_user, {"genres": ["Racing"]})

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=admin_user.id
    )

    assert {rom.id for rom in roms} == {rom.id for rom in matching}


def test_filter_roms_by_smart_collection_narrows_with_the_gallery_filters(
    platform: Platform, admin_user: User
):
    _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]})
    keeper = _add_rom(
        platform, "Rally Two", manual_metadata={"genres": ["Racing"]}, regions=["USA"]
    )
    _add_rom(
        platform, "Puzzler", manual_metadata={"genres": ["Puzzle"]}, regions=["USA"]
    )

    smart_collection = _add_smart_collection(admin_user, {"genres": ["Racing"]})

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id,
        regions=["USA"],
        user_id=admin_user.id,
    )

    assert {rom.id for rom in roms} == {keeper.id}


def test_filter_roms_by_smart_collection_keeps_both_search_terms(
    platform: Platform, admin_user: User
):
    # The collection's own search term and the gallery's are separate fulltext
    # clauses in one statement; they must not share a bind parameter name.
    match_both = _add_rom(platform, "Rally Champion")
    _add_rom(platform, "Rally Junior")
    _add_rom(platform, "Champion Cup")

    smart_collection = _add_smart_collection(admin_user, {"search_term": "rally"})

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id,
        search_term="champion",
        user_id=admin_user.id,
    )

    assert {rom.id for rom in roms} == {match_both.id}


def test_filter_roms_by_smart_collection_resolves_per_viewer(
    platform: Platform, admin_user: User, editor_user: User
):
    # A public smart collection built on a per-user filter must answer for the
    # viewer, not for whoever opened it last.
    admin_pick = _add_rom(platform, "Admin Pick")
    editor_pick = _add_rom(platform, "Editor Pick")
    _favorite(admin_user, [admin_pick])
    _favorite(editor_user, [editor_pick])

    smart_collection = _add_smart_collection(
        admin_user, {"favorite": True}, is_public=True
    )

    admin_roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=admin_user.id
    )
    editor_roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=editor_user.id
    )

    assert {rom.id for rom in admin_roms} == {admin_pick.id}
    assert {rom.id for rom in editor_roms} == {editor_pick.id}


def test_filter_roms_by_smart_collection_scoped_to_a_regular_collection(
    platform: Platform, admin_user: User
):
    inside = _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]})
    _add_rom(platform, "Rally Two", manual_metadata={"genres": ["Racing"]})

    collection = db_collection_handler.add_collection(
        Collection(name="Shelf", description="", user_id=admin_user.id)
    )
    db_collection_handler.add_roms_to_collection(collection.id, [inside.id])

    smart_collection = _add_smart_collection(
        admin_user, {"genres": ["Racing"], "collection_id": collection.id}
    )

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=admin_user.id
    )

    assert {rom.id for rom in roms} == {inside.id}


def test_filter_roms_by_smart_collection_with_joined_criteria(
    platform: Platform, admin_user: User
):
    # `playable` joins platforms and `has_soundtrack` is a correlated column
    # property; both have to survive being applied to a bare-column subquery.
    rom = _add_rom(platform, "Rally One")

    smart_collection = _add_smart_collection(
        admin_user, {"playable": False, "has_soundtrack": False, "missing": False}
    )

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=admin_user.id
    )

    assert {result.id for result in roms} == {rom.id}


def test_filter_roms_by_unknown_smart_collection_returns_nothing(
    platform: Platform, admin_user: User
):
    _add_rom(platform, "Rally One")

    roms = db_rom_handler.get_roms_scalar(
        smart_collection_id=123456, user_id=admin_user.id
    )

    assert list(roms) == []


def test_refresh_smart_collection_updates_the_cached_columns(
    platform: Platform, admin_user: User
):
    # The cached columns back the collections list and the ROM detail page.
    smart_collection = _add_smart_collection(admin_user, {"genres": ["Racing"]})
    assert smart_collection.rom_count == 0

    roms = [
        _add_rom(
            platform,
            f"Rally {index}",
            cover=f"cover_{index}.png",
            manual_metadata={"genres": ["Racing"]},
        )
        for index in range(3)
    ]

    refreshed = db_collection_handler.refresh_smart_collection(smart_collection.id)

    assert refreshed is not None
    assert refreshed.rom_count == 3
    assert set(refreshed.rom_ids) == {rom.id for rom in roms}
    assert len(refreshed.path_covers_small) == 3
    assert len(refreshed.path_covers_large) == 3


def test_refresh_smart_collection_is_a_noop_when_nothing_moved(
    platform: Platform, admin_user: User, mocker
):
    # Rewriting an unchanged collection would bump `updated_at`, the `?ts=`
    # cover cache-buster that clients also sync on.
    smart_collection = _add_smart_collection(admin_user, {"genres": ["Racing"]})
    _add_rom(
        platform,
        "Rally One",
        cover="cover_0.png",
        manual_metadata={"genres": ["Racing"]},
    )
    first = db_collection_handler.refresh_smart_collection(smart_collection.id)
    assert first is not None
    assert len(first.path_covers_small) == 1

    update = mocker.spy(db_collection_handler, "update_smart_collection")
    second = db_collection_handler.refresh_smart_collection(smart_collection.id)

    assert update.call_count == 0
    assert second is not None
    assert second.path_covers_small == first.path_covers_small


def test_refresh_smart_collections_covers_every_collection(
    platform: Platform, admin_user: User
):
    racing = _add_smart_collection(admin_user, {"genres": ["Racing"]}, name="Racing")
    puzzle = _add_smart_collection(admin_user, {"genres": ["Puzzle"]}, name="Puzzle")
    _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]})
    _add_rom(platform, "Puzzler", manual_metadata={"genres": ["Puzzle"]})
    _add_rom(platform, "Puzzler Two", manual_metadata={"genres": ["Puzzle"]})

    db_collection_handler.refresh_smart_collections()

    refreshed_racing = db_collection_handler.get_smart_collection(racing.id)
    refreshed_puzzle = db_collection_handler.get_smart_collection(puzzle.id)
    assert refreshed_racing is not None and refreshed_racing.rom_count == 1
    assert refreshed_puzzle is not None and refreshed_puzzle.rom_count == 2


def test_refresh_for_roms_updates_the_collections_the_rom_moved_between(
    platform: Platform, admin_user: User
):
    racing = _add_smart_collection(admin_user, {"genres": ["Racing"]}, name="Racing")
    puzzle = _add_smart_collection(admin_user, {"genres": ["Puzzle"]}, name="Puzzle")
    _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]})
    mover = _add_rom(platform, "Puzzler", manual_metadata={"genres": ["Puzzle"]})
    db_collection_handler.refresh_smart_collections()

    db_rom_handler.update_rom(mover.id, {"manual_metadata": {"genres": ["Racing"]}})
    db_collection_handler.refresh_smart_collections_for_roms([mover.id])

    racing_after = db_collection_handler.get_smart_collection(racing.id)
    puzzle_after = db_collection_handler.get_smart_collection(puzzle.id)
    assert racing_after is not None and racing_after.rom_count == 2
    assert puzzle_after is not None and puzzle_after.rom_count == 0


def test_refresh_for_roms_leaves_untouched_collections_alone(
    platform: Platform, admin_user: User, mocker
):
    # Recounting every collection for one edited ROM would scan the library
    # once per collection, which is the cost this issue is about.
    _add_smart_collection(admin_user, {"genres": ["Racing"]}, name="Racing")
    _add_rom(platform, "Rally One", manual_metadata={"genres": ["Racing"]})
    db_collection_handler.refresh_smart_collections()
    bystander = _add_rom(platform, "Puzzler", manual_metadata={"genres": ["Puzzle"]})

    refresh = mocker.spy(db_collection_handler, "refresh_smart_collection")
    db_collection_handler.refresh_smart_collections_for_roms([bystander.id])

    assert refresh.call_count == 0


def _add_save(rom: Rom, user: User, name: str = "save.sav") -> Save:
    return db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=user.id,
            file_name=name,
            file_name_no_tags=name,
            file_name_no_ext=name,
            file_extension="sav",
            emulator="test_emulator",
            file_path="test/saves",
            file_size_bytes=1.0,
        )
    )


def test_refresh_for_roms_follows_per_user_state(platform: Platform, admin_user: User):
    # A save is not a ROM edit, but it moves anything filtering on `has_saves`.
    collection = _add_smart_collection(admin_user, {"has_saves": True})
    rom = _add_rom(platform, "Rally One")
    db_collection_handler.refresh_smart_collections()
    seeded = db_collection_handler.get_smart_collection(collection.id)
    assert seeded is not None and seeded.rom_count == 0

    _add_save(rom, admin_user)
    db_collection_handler.refresh_smart_collections_for_roms(
        [rom.id], membership_only=True
    )

    after = db_collection_handler.get_smart_collection(collection.id)
    assert after is not None
    assert after.rom_ids == [rom.id]


def test_refresh_for_roms_membership_only_skips_a_member_that_stayed(
    platform: Platform, admin_user: User, mocker
):
    # Autosaves land constantly. Once the ROM is already a member, another save
    # changes nothing about the collection, so it must not force a recount.
    _add_smart_collection(admin_user, {"has_saves": True})
    rom = _add_rom(platform, "Rally One")
    _add_save(rom, admin_user, "first.sav")
    db_collection_handler.refresh_smart_collections()

    _add_save(rom, admin_user, "second.sav")
    refresh = mocker.spy(db_collection_handler, "refresh_smart_collection")
    db_collection_handler.refresh_smart_collections_for_roms(
        [rom.id], membership_only=True
    )

    assert refresh.call_count == 0


def test_cached_membership_belongs_to_the_owner(
    platform: Platform, admin_user: User, editor_user: User
):
    # The cached columns live on the shared row, so they must describe the
    # owner's view of a per-user filter rather than the last viewer's.
    admin_pick = _add_rom(platform, "Admin Pick")
    editor_pick = _add_rom(platform, "Editor Pick")
    _favorite(admin_user, [admin_pick])
    _favorite(editor_user, [editor_pick])

    smart_collection = _add_smart_collection(
        admin_user, {"favorite": True}, is_public=True
    )

    db_rom_handler.get_roms_scalar(
        smart_collection_id=smart_collection.id, user_id=editor_user.id
    )
    refreshed = db_collection_handler.refresh_smart_collection(smart_collection.id)

    assert refreshed is not None
    assert set(refreshed.rom_ids) == {admin_pick.id}
