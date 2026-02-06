from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from handler.auth import auth_handler
from handler.database import (
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom
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
    # Create additional ROMs for testing
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
    assert new_user.role == Role.VIEWER
    assert new_user.enabled

    db_user_handler.update_user(new_user.id, {"role": Role.EDITOR})

    new_user = db_user_handler.get_user(new_user.id)
    assert new_user is not None
    assert new_user.role == Role.EDITOR

    db_user_handler.delete_user(new_user.id)

    all_users = db_user_handler.get_users()
    assert len(all_users) == 1

    try:
        new_user = db_user_handler.add_user(
            User(
                username="test_admin",
                hashed_password=auth_handler.get_password_hash("new_password"),
                role=Role.ADMIN,
            )
        )
    except IntegrityError as e:
        assert "Duplicate entry 'test_admin' for key" in str(e)


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
