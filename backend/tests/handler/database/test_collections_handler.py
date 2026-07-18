from handler.database import db_collection_handler, db_rom_handler
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _add_rom(platform: Platform, index: int, manual_metadata: dict) -> Rom:
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
    )
    return db_rom_handler.add_rom(rom)


def test_get_virtual_collections_includes_manual_franchises(
    platform: Platform, admin_user: User
):
    # The virtual_collections view sources from roms_metadata, so manually-set
    # franchises (with no IGDB match) must generate a franchise collection once
    # shared by more than 2 ROMs.
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


def test_get_smart_collection_roms_normalizes_legacy_selected_status_lists(
    admin_user: User, mocker
):
    get_roms_scalar = mocker.patch("handler.database.db_rom_handler.get_roms_scalar")
    smart_collection = SmartCollection(
        name="Finished games",
        description="",
        user_id=admin_user.id,
        filter_criteria={"selected_status": ["finished", "completed_100"]},
    )

    db_collection_handler.get_smart_collection_roms(
        smart_collection, user_id=admin_user.id
    )

    assert get_roms_scalar.call_args.kwargs["statuses"] == [
        "finished",
        "completed_100",
    ]


def test_get_smart_collection_roms_passes_metadata_providers(admin_user: User, mocker):
    get_roms_scalar = mocker.patch("handler.database.db_rom_handler.get_roms_scalar")
    smart_collection = SmartCollection(
        name="IGDB and Moby matches",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "metadata_providers": ["igdb", "moby"],
            "metadata_providers_logic": "all",
        },
    )

    db_collection_handler.get_smart_collection_roms(
        smart_collection, user_id=admin_user.id
    )

    assert get_roms_scalar.call_args.kwargs["metadata_providers"] == ["igdb", "moby"]
    assert get_roms_scalar.call_args.kwargs["metadata_providers_logic"] == "all"


def test_get_smart_collection_roms_passes_tags(admin_user: User, mocker):
    get_roms_scalar = mocker.patch("handler.database.db_rom_handler.get_roms_scalar")
    smart_collection = SmartCollection(
        name="Prototypes and betas",
        description="",
        user_id=admin_user.id,
        filter_criteria={
            "tags": ["Proto", "Beta"],
            "tags_logic": "any",
        },
    )

    db_collection_handler.get_smart_collection_roms(
        smart_collection, user_id=admin_user.id
    )

    assert get_roms_scalar.call_args.kwargs["tags"] == ["Proto", "Beta"]
    assert get_roms_scalar.call_args.kwargs["tags_logic"] == "any"
