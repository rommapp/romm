from sqlalchemy.exc import IntegrityError

from handler.db_handler import DBHandler
from models import Platform, Rom, User
from models.user import Role
from utils.auth import get_password_hash

dbh = DBHandler()


def test_platforms():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    dbh.add_platform(platform)

    platforms = dbh.get_platforms()
    assert len(platforms) == 1

    platform = dbh.get_platform(platform.slug)
    assert platform.name == "test_platform"

    dbh.purge_platforms([])
    platforms = dbh.get_platforms()
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
            file_size=1.0,
            file_size_units="MB",
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

    dbh.purge_roms(rom_2.platform_slug, [rom_2.slug])

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
            hashed_password=get_password_hash("new_password"),
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
                hashed_password=get_password_hash("new_password"),
                role=Role.ADMIN,
            )
        )
    except IntegrityError as e:
        assert "Duplicate entry 'test_admin' for key" in str(e)
