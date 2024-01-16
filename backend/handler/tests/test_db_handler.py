from sqlalchemy.exc import IntegrityError

# from handler.db_handler import DBHandler
from models import Platform, Rom, User, Save, State, Screenshot
from models.user import Role
from handler import dbh, authh

# dbh = DBHandler()


def test_platforms():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    dbh.add_platform(platform)

    platforms = dbh.get_platform()
    assert len(platforms) == 1

    platform = dbh.get_platform(platform.slug)
    assert platform.name == "test_platform"

    dbh.purge_platforms([])
    platforms = dbh.get_platform()
    assert len(platforms) == 0


def test_roms(rom):
    dbh.add_rom(
        Rom(
            name="test_rom_2",
            slug="test_rom_slug_2",
            platform_slug=rom.platform_slug,
            file_name="test_rom_2",
            file_name_no_tags="test_rom_2",
            file_extension="zip",
            file_path=f"{rom.platform_slug}/roms",
            file_size_bytes=1000.0,
        )
    )

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms(rom.platform_slug)).all()
        assert len(roms) == 2

    rom = dbh.get_rom(roms[0].id)
    assert rom.file_name == "test_rom.zip"

    dbh.update_rom(roms[1].id, {"file_name": "test_rom_2_updated"})
    rom_2 = dbh.get_rom(roms[1].id)
    assert rom_2.file_name == "test_rom_2_updated"

    dbh.delete_rom(rom.id)

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms(rom.platform_slug)).all()
        assert len(roms) == 1

    dbh.purge_roms(rom_2.platform_slug, [rom_2.id])

    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms(rom.platform_slug)).all()
        assert len(roms) == 0


def test_utils(rom):
    with dbh.session.begin() as session:
        roms = session.scalars(dbh.get_roms(rom.platform_slug)).all()
        assert (
            dbh.get_rom_by_filename(rom.platform_slug, rom.file_name).id == roms[0].id
        )


def test_users(admin_user):
    dbh.add_user(
        User(
            username="new_user",
            hashed_password=authh.get_password_hash("new_password"),
        )
    )

    all_users = dbh.get_users()
    assert len(all_users) == 2

    new_user = dbh.get_user_by_username("new_user")
    assert new_user.username == "new_user"
    assert new_user.role == Role.VIEWER
    assert new_user.enabled

    dbh.update_user(new_user.id, {"role": Role.EDITOR})

    new_user = dbh.get_user(new_user.id)
    assert new_user.role == Role.EDITOR

    dbh.delete_user(new_user.id)

    all_users = dbh.get_users()
    assert len(all_users) == 1

    try:
        new_user = dbh.add_user(
            User(
                username="test_admin",
                hashed_password=authh.get_password_hash("new_password"),
                role=Role.ADMIN,
            )
        )
    except IntegrityError as e:
        assert "Duplicate entry 'test_admin' for key" in str(e)


def test_saves(save):
    dbh.add_save(
        Save(
            rom_id=save.rom_id,
            platform_slug=save.platform_slug,
            file_name="test_save_2.sav",
            file_name_no_tags="test_save_2",
            file_extension="sav",
            emulator="test_emulator",
            file_path=f"{save.platform_slug}/saves/test_emulator",
            file_size_bytes=1.0,
        )
    )

    rom = dbh.get_rom(save.rom_id)
    assert len(rom.saves) == 2

    save = dbh.get_save(rom.saves[0].id)
    assert save.file_name == "test_save.sav"

    dbh.update_save(save.id, {"file_name": "test_save_2.sav"})
    save = dbh.get_save(save.id)
    assert save.file_name == "test_save_2.sav"

    dbh.delete_save(save.id)

    rom = dbh.get_rom(save.rom_id)
    assert len(rom.saves) == 1


def test_states(state):
    dbh.add_state(
        State(
            rom_id=state.rom_id,
            platform_slug=state.platform_slug,
            file_name="test_state_2.state",
            file_name_no_tags="test_state_2",
            file_extension="state",
            file_path=f"{state.platform_slug}/states",
            file_size_bytes=1.0,
        )
    )

    rom = dbh.get_rom(state.rom_id)
    assert len(rom.states) == 2

    state = dbh.get_state(rom.states[0].id)
    assert state.file_name == "test_state.state"

    dbh.update_state(state.id, {"file_name": "test_state_2.state"})
    state = dbh.get_state(state.id)
    assert state.file_name == "test_state_2.state"

    dbh.delete_state(state.id)

    rom = dbh.get_rom(state.rom_id)
    assert len(rom.states) == 1


def test_screenshots(screenshot):
    dbh.add_screenshot(
        Screenshot(
            rom_id=screenshot.rom_id,
            platform_slug=screenshot.platform_slug,
            file_name="test_screenshot_2.png",
            file_name_no_tags="test_screenshot_2",
            file_extension="png",
            file_path=f"{screenshot.platform_slug}/screenshots",
            file_size_bytes=1.0,
        )
    )

    rom = dbh.get_rom(screenshot.rom_id)
    assert len(rom.screenshots) == 2

    screenshot = dbh.get_screenshot(rom.screenshots[0].id)
    assert screenshot.file_name == "test_screenshot.png"

    dbh.update_screenshot(screenshot.id, {"file_name": "test_screenshot_2.png"})
    screenshot = dbh.get_screenshot(screenshot.id)
    assert screenshot.file_name == "test_screenshot_2.png"

    dbh.delete_screenshot(screenshot.id)

    rom = dbh.get_rom(screenshot.rom_id)
    assert len(rom.screenshots) == 1
