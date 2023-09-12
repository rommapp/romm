import pytest
import alembic.config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.config_loader import ConfigLoader
from models import Platform, Rom, User
from models.user import Role
from utils.auth import get_password_hash
from .. import dbh

engine = create_engine(ConfigLoader.get_db_engine(), pool_pre_ping=True)
session = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    alembic.config.main(argv=["upgrade", "head"])


@pytest.fixture(autouse=True)
def clear_database():
    with session.begin() as s:
        s.query(Rom).delete(synchronize_session="evaluate")
        s.query(Platform).delete(synchronize_session="evaluate")
        s.query(User).delete(synchronize_session="evaluate")


@pytest.fixture
def platform():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    return dbh.add_platform(platform)


@pytest.fixture
def rom(platform):
    rom = Rom(
        name="test_rom",
        slug="test_rom_slug",
        platform_slug="test_platform_slug",
        file_name="test_rom",
        file_name_no_tags="test_rom",
        file_extension="zip",
        file_path="test_platform_slug/roms",
        file_size=1.0,
        file_size_units="MB",
    )
    return dbh.add_rom(rom)


@pytest.fixture
def admin_user():
    user = User(
        username="test_admin",
        hashed_password=get_password_hash("test_admin_password"),
        role=Role.ADMIN,
    )
    return dbh.add_user(user)


@pytest.fixture
def editor_user():
    user = User(
        username="test_editor",
        hashed_password=get_password_hash("test_editor_password"),
        role=Role.EDITOR,
    )
    return dbh.add_user(user)


@pytest.fixture
def viewer_user():
    user = User(
        username="test_viewer",
        hashed_password=get_password_hash("test_viewer_password"),
        role=Role.VIEWER,
    )
    return dbh.add_user(user)
