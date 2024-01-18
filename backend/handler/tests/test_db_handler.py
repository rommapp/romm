from sqlalchemy.exc import IntegrityError

# from handler.db_handler import DBHandler
from models import Platform, Rom, User, Save, State, Screenshot
from models.user import Role
from handler import authh, dbplatformh, dbromh, dbuserh, dbsaveh, dbstateh, dbscreenshotsh


def test_platforms():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    dbplatformh.add_platform(platform)

    platforms = dbplatformh.get_platforms()
    assert len(platforms) == 1

    platform = dbplatformh.get_platform_by_slug(platform.slug)
    assert platform.name == "test_platform"

    dbplatformh.purge_platforms([])
    platforms = dbplatformh.get_platforms()
    assert len(platforms) == 0


def test_roms(rom: Rom, platform: Platform):
    dbromh.add_rom(
        Rom(
            platform_id=rom.platform_id,
            name="test_rom_2",
            slug="test_rom_slug_2",
            file_name="test_rom_2",
            file_name_no_tags="test_rom_2",
            file_extension="zip",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=1000.0,
        )
    )

    with dbromh.session.begin() as session:
        roms = session.scalars(dbromh.get_roms(platform_id=platform.id)).all()
        assert len(roms) == 2

    rom = dbromh.get_roms(id=roms[0].id)
    assert rom.file_name == "test_rom.zip"

    dbromh.update_rom(roms[1].id, {"file_name": "test_rom_2_updated"})
    rom_2 = dbromh.get_roms(id=roms[1].id)
    assert rom_2.file_name == "test_rom_2_updated"

    dbromh.delete_rom(rom.id)

    with dbromh.session.begin() as session:
        roms = session.scalars(dbromh.get_roms(platform_id=platform.id)).all()
        assert len(roms) == 1

    dbromh.purge_roms(rom_2.platform_id, [rom_2.id])

    with dbromh.session.begin() as session:
        roms = session.scalars(dbromh.get_roms(platform_id=platform.id)).all()
        assert len(roms) == 0


def test_utils(rom: Rom, platform: Platform):
    with dbromh.session.begin() as session:
        roms = session.scalars(dbromh.get_roms(platform_id=platform.id)).all()
        assert (
            dbromh.get_rom_by_filename(platform_id=platform.id, file_name=rom.file_name).id == roms[0].id
        )


def test_users(admin_user):
    dbuserh.add_user(
        User(
            username="new_user",
            hashed_password=authh.get_password_hash("new_password"),
        )
    )

    all_users = dbuserh.get_users()
    assert len(all_users) == 2

    new_user = dbuserh.get_user_by_username("new_user")
    assert new_user.username == "new_user"
    assert new_user.role == Role.VIEWER
    assert new_user.enabled

    dbuserh.update_user(new_user.id, {"role": Role.EDITOR})

    new_user = dbuserh.get_user(new_user.id)
    assert new_user.role == Role.EDITOR

    dbuserh.delete_user(new_user.id)

    all_users = dbuserh.get_users()
    assert len(all_users) == 1

    try:
        new_user = dbuserh.add_user(
            User(
                username="test_admin",
                hashed_password=authh.get_password_hash("new_password"),
                role=Role.ADMIN,
            )
        )
    except IntegrityError as e:
        assert "Duplicate entry 'test_admin' for key" in str(e)


def test_saves(save: Save, platform: Platform):
    dbsaveh.add_save(
        Save(
            rom_id=save.rom_id,
            file_name="test_save_2.sav",
            file_name_no_tags="test_save_2",
            file_extension="sav",
            emulator="test_emulator",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=1.0,
        )
    )

    rom = dbromh.get_roms(id=save.rom_id)
    assert len(rom.saves) == 2

    save = dbsaveh.get_save(rom.saves[0].id)
    assert save.file_name == "test_save.sav"

    dbsaveh.update_save(save.id, {"file_name": "test_save_2.sav"})
    save = dbsaveh.get_save(save.id)
    assert save.file_name == "test_save_2.sav"

    dbsaveh.delete_save(save.id)

    rom = dbromh.get_roms(id=save.rom_id)
    assert len(rom.saves) == 1


def test_states(state: State, platform: Platform):
    dbstateh.add_state(
        State(
            rom_id=state.rom_id,
            file_name="test_state_2.state",
            file_name_no_tags="test_state_2",
            file_extension="state",
            file_path=f"{platform.slug}/states",
            file_size_bytes=1.0,
        )
    )

    rom = dbromh.get_roms(id=state.rom_id)
    assert len(rom.states) == 2

    state = dbstateh.get_state(rom.states[0].id)
    assert state.file_name == "test_state.state"

    dbstateh.update_state(state.id, {"file_name": "test_state_2.state"})
    state = dbstateh.get_state(state.id)
    assert state.file_name == "test_state_2.state"

    dbstateh.delete_state(state.id)

    rom = dbromh.get_roms(id=state.rom_id)
    assert len(rom.states) == 1


def test_screenshots(screenshot: Screenshot, platform: Platform):
    dbscreenshotsh.add_screenshot(
        Screenshot(
            rom_id=screenshot.rom_id,
            file_name="test_screenshot_2.png",
            file_name_no_tags="test_screenshot_2",
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=1.0,
        )
    )

    rom = dbromh.get_roms(id=screenshot.rom_id)
    assert len(rom.screenshots) == 2

    screenshot = dbscreenshotsh.get_screenshot(rom.screenshots[0].id)
    assert screenshot.file_name == "test_screenshot.png"

    dbscreenshotsh.update_screenshot(screenshot.id, {"file_name": "test_screenshot_2.png"})
    screenshot = dbscreenshotsh.get_screenshot(screenshot.id)
    assert screenshot.file_name == "test_screenshot_2.png"

    dbscreenshotsh.delete_screenshot(screenshot.id)

    rom = dbromh.get_roms(id=screenshot.rom_id)
    assert len(rom.screenshots) == 1
