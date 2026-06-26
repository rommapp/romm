from handler.database import db_collection_handler
from models.collection import SmartCollection
from models.user import User


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
