from handler.database import db_collection_handler, db_rom_handler
from handler.database.collections_handler import MAX_VIRTUAL_COLLECTION_COVERS
from models.collection import Collection, SmartCollection
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _add_rom(
    platform: Platform, index: int, manual_metadata: dict, cover: str | None = None
) -> Rom:
    rom = Rom(
        platform_id=platform.id,
        name=f"manual_rom_{index}",
        slug=f"manual_rom_{index}",
        fs_name=f"manual_rom_{index}.zip",
        fs_name_no_tags=f"manual_rom_{index}",
        fs_name_no_ext=f"manual_rom_{index}",
        fs_extension="zip",
        fs_path=f"{platform.slug}/roms",
        manual_metadata=manual_metadata,
        path_cover_s=cover or "",
        path_cover_l=cover or "",
    )
    return db_rom_handler.add_rom(rom)


def _virtual_collection(type: str, name: str):
    return next(
        (
            c
            for c in db_collection_handler.get_virtual_collections(type=type)
            if c.name == name
        ),
        None,
    )


def test_get_virtual_collections_includes_manual_franchises(
    platform: Platform, admin_user: User
):
    # The virtual_collections view sources from the generated metadata columns,
    # so manually-set franchises (with no IGDB match) must generate a franchise
    # collection once shared by more than 2 ROMs.
    for index in range(3):
        _add_rom(platform, index, {"franchises": ["Grow"]})

    collections = db_collection_handler.get_virtual_collections(type="franchise")

    grow = next((c for c in collections if c.name == "Grow"), None)
    assert grow is not None
    assert grow.type == "franchise"
    assert len(grow.rom_ids) == 3


def test_get_virtual_collections_respects_min_rom_threshold(
    platform: Platform, admin_user: User
):
    # Fewer than 3 ROMs sharing a value must not surface as a collection.
    for index in range(2):
        _add_rom(platform, index, {"franchises": ["Sparse"]})

    collections = db_collection_handler.get_virtual_collections(type="franchise")

    assert all(c.name != "Sparse" for c in collections)


def test_virtual_collection_membership_follows_metadata_edits(
    platform: Platform, admin_user: User
):
    # Membership is maintained by triggers on roms, so editing metadata must
    # move the rom between collections with no rebuild step in between.
    roms = [_add_rom(platform, index, {"genres": ["Shmup"]}) for index in range(3)]

    assert _virtual_collection("genre", "Shmup") is not None

    for rom in roms:
        db_rom_handler.update_rom(rom.id, {"manual_metadata": {"genres": ["Puzzle"]}})

    assert _virtual_collection("genre", "Shmup") is None

    puzzle = _virtual_collection("genre", "Puzzle")
    assert puzzle is not None
    assert set(puzzle.rom_ids) == {rom.id for rom in roms}


def test_virtual_collection_membership_drops_deleted_roms(
    platform: Platform, admin_user: User
):
    roms = [_add_rom(platform, index, {"genres": ["Pinball"]}) for index in range(4)]

    db_rom_handler.delete_rom(roms[0].id)

    pinball = _virtual_collection("genre", "Pinball")
    assert pinball is not None
    assert set(pinball.rom_ids) == {rom.id for rom in roms[1:]}


def test_get_virtual_collection_by_id_returns_covers(
    platform: Platform, admin_user: User
):
    roms = [
        _add_rom(platform, index, {"genres": ["Racing"]}, cover=f"cover_{index}.png")
        for index in range(3)
    ]
    collection = _virtual_collection("genre", "Racing")
    assert collection is not None

    by_id = db_collection_handler.get_virtual_collection(collection.id)

    assert by_id is not None
    assert set(by_id.rom_ids) == {rom.id for rom in roms}
    assert sorted(by_id.path_covers_s) == [f"cover_{index}.png" for index in range(3)]


def test_virtual_collection_covers_are_capped(platform: Platform, admin_user: User):
    for index in range(MAX_VIRTUAL_COLLECTION_COVERS + 3):
        _add_rom(platform, index, {"genres": ["Rhythm"]}, cover=f"cover_{index}.png")

    collection = _virtual_collection("genre", "Rhythm")

    assert collection is not None
    assert len(collection.path_covers_s) == MAX_VIRTUAL_COLLECTION_COVERS
    assert len(collection.path_covers_l) == MAX_VIRTUAL_COLLECTION_COVERS


def test_filter_roms_by_virtual_collection(platform: Platform, admin_user: User):
    in_collection = [
        _add_rom(platform, index, {"genres": ["Metroidvania"]}) for index in range(3)
    ]
    _add_rom(platform, 99, {"genres": ["Sports"]})

    collection = _virtual_collection("genre", "Metroidvania")
    assert collection is not None

    roms = db_rom_handler.get_roms_scalar(virtual_collection_id=collection.id)

    assert {rom.id for rom in roms} == {rom.id for rom in in_collection}


def test_filter_roms_by_collection(platform: Platform, admin_user: User):
    in_collection = [_add_rom(platform, index, {}) for index in range(3)]
    outside = _add_rom(platform, 99, {})

    collection = db_collection_handler.add_collection(
        Collection(name="Shelf", description="", user_id=admin_user.id)
    )
    db_collection_handler.add_roms_to_collection(
        collection.id, [rom.id for rom in in_collection]
    )

    roms = db_rom_handler.get_roms_scalar(collection_id=collection.id)

    assert {rom.id for rom in roms} == {rom.id for rom in in_collection}
    assert outside.id not in {rom.id for rom in roms}


def test_filter_roms_by_unknown_collection_returns_nothing(
    platform: Platform, admin_user: User
):
    # A stale bookmark must not fall through to the whole library.
    _add_rom(platform, 0, {})

    roms = db_rom_handler.get_roms_scalar(collection_id=123456)

    assert list(roms) == []


def test_filter_roms_by_favorite_follows_the_users_own_collection(
    platform: Platform, admin_user: User, editor_user: User
):
    admin_pick = _add_rom(platform, 0, {})
    editor_pick = _add_rom(platform, 1, {})

    for user, rom in ((admin_user, admin_pick), (editor_user, editor_pick)):
        favorites = db_collection_handler.add_collection(
            Collection(
                name=f"Favorites {user.id}",
                description="",
                user_id=user.id,
                is_favorite=True,
            )
        )
        db_collection_handler.add_roms_to_collection(favorites.id, [rom.id])

    admin_roms = db_rom_handler.get_roms_scalar(favorite=True, user_id=admin_user.id)
    editor_roms = db_rom_handler.get_roms_scalar(favorite=True, user_id=editor_user.id)

    assert {rom.id for rom in admin_roms} == {admin_pick.id}
    assert {rom.id for rom in editor_roms} == {editor_pick.id}


def test_filter_roms_by_non_favorite_without_a_collection(
    platform: Platform, admin_user: User
):
    roms = [_add_rom(platform, index, {}) for index in range(2)]

    not_favorites = db_rom_handler.get_roms_scalar(
        favorite=False, user_id=admin_user.id
    )

    assert {rom.id for rom in not_favorites} == {rom.id for rom in roms}


def test_get_smart_collection_criteria_normalizes_legacy_selected_status_lists(
    admin_user: User,
):
    smart_collection = SmartCollection(
        name="Finished games",
        description="",
        user_id=admin_user.id,
        filter_criteria={"selected_status": ["finished", "completed_100"]},
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["statuses"] == ["finished", "completed_100"]


def test_get_smart_collection_criteria_wraps_legacy_scalar_values(admin_user: User):
    smart_collection = SmartCollection(
        name="Legacy shooter",
        description="",
        user_id=admin_user.id,
        filter_criteria={"selected_genre": "Shooter", "platform_id": 7},
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["genres"] == ["Shooter"]
    assert criteria["platform_ids"] == [7]


def test_get_smart_collection_criteria_passes_metadata_providers(admin_user: User):
    smart_collection = SmartCollection(
        name="IGDB and Moby matches",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "metadata_providers": ["igdb", "moby"],
            "metadata_providers_logic": "all",
        },
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["metadata_providers"] == ["igdb", "moby"]
    assert criteria["metadata_providers_logic"] == "all"


def test_get_smart_collection_criteria_passes_asset_and_soundtrack_filters(
    admin_user: User,
):
    smart_collection = SmartCollection(
        name="Games with saves and music",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "has_saves": True,
            "has_states": True,
            "has_soundtrack": True,
        },
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["has_saves"] is True
    assert criteria["has_states"] is True
    assert criteria["has_soundtrack"] is True


def test_get_smart_collection_criteria_passes_negative_boolean_filters(
    admin_user: User,
):
    smart_collection = SmartCollection(
        name="Unmatched games",
        description="",
        user_id=admin_user.id,
        filter_criteria={"matched": False},
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["matched"] is False


def test_get_smart_collection_criteria_passes_player_counts(admin_user: User):
    smart_collection = SmartCollection(
        name="Multiplayer games",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "player_counts": ["2", "4"],
            "player_counts_logic": "any",
        },
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["player_counts"] == ["2", "4"]
    assert criteria["player_counts_logic"] == "any"


def test_get_smart_collection_criteria_passes_tags(admin_user: User):
    smart_collection = SmartCollection(
        name="Prototypes and betas",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "tags": ["Proto", "Beta"],
            "tags_logic": "any",
        },
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert criteria["tags"] == ["Proto", "Beta"]
    assert criteria["tags_logic"] == "any"


def test_get_smart_collection_criteria_drops_nested_smart_collection_id(
    admin_user: User,
):
    # The v2 dialog stores the route it was created from, so a smart collection
    # built while viewing another one carries its id. Membership never nests.
    smart_collection = SmartCollection(
        name="Nested",
        description="",
        user_id=admin_user.id,
        filter_criteria={"smart_collection_id": 42, "matched": True},
    )

    criteria = db_collection_handler.get_smart_collection_criteria(smart_collection)

    assert "smart_collection_id" not in criteria
    assert criteria["matched"] is True
