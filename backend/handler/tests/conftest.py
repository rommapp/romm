import pytest
import alembic.config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.config_loader import ConfigLoader
from models import Platform, Rom, User
from models.user import Role

engine = create_engine(ConfigLoader.get_db_engine(), pool_pre_ping=True)
session = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    alembic.config.main(argv=["upgrade", "head"])


@pytest.fixture(autouse=True)
def clear_database():
    with session.begin() as s:
        s.query(Platform).delete(synchronize_session="evaluate")
        s.query(Rom).delete(synchronize_session="evaluate")
        s.query(User).delete(synchronize_session="evaluate")


@pytest.fixture
def platform():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform"
    )
    with session.begin() as s:
        s.merge(platform)
    return platform


@pytest.fixture
def rom(platform):
    rom = Rom(
        r_name="test_rom",
        r_slug="test_rom_slug",
        p_name="test_platform",
        p_slug="test_platform_slug",
        file_name="test_rom",
        file_name_no_tags="test_rom",
        file_path="test_platform_slug/roms",
    )
    with session.begin() as s:
        s.merge(rom)
    return rom


@pytest.fixture
def admin_user():
    user = User(
        username="test_admin_user",
        hashed_password="test_password",
        role=Role.ADMIN,
    )
    with session.begin() as s:
        s.merge(user)
    return user


@pytest.fixture
def editor_user():
    user = User(
        username="test_editor_user",
        hashed_password="test_password",
        role=Role.EDITOR,
    )
    with session.begin() as s:
        s.merge(user)
    return user


@pytest.fixture
def user():
    user = User(
        username="test_user",
        hashed_password="test_password",
        role=Role.VIEWER,
    )
    with session.begin() as s:
        s.merge(user)
    return user
