import pytest
import alembic.config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.config_manager import ConfigManager
from models import Platform, Rom, User, Save, State, Screenshot
from models.user import Role
from handler import dbuserh, dbplatformh, dbromh, dbsaveh, dbstateh, authh, dbscreenshotsh

engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
session = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    alembic.config.main(argv=["upgrade", "head"])


@pytest.fixture(autouse=True)
def clear_database():
    with session.begin() as s:
        s.query(Save).delete(synchronize_session="evaluate")
        s.query(State).delete(synchronize_session="evaluate")
        s.query(Screenshot).delete(synchronize_session="evaluate")
        s.query(Rom).delete(synchronize_session="evaluate")
        s.query(Platform).delete(synchronize_session="evaluate")
        s.query(User).delete(synchronize_session="evaluate")


@pytest.fixture
def platform():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    return dbplatformh.add_platform(platform)


@pytest.fixture
def rom(platform: Platform):
    rom = Rom(
        platform_id=platform.id,
        name="test_rom",
        slug="test_rom_slug",
        file_name="test_rom.zip",
        file_name_no_tags="test_rom",
        file_extension="zip",
        file_path=f"{platform.slug}/roms",
        file_size_bytes=1000.0,
    )
    return dbromh.add_rom(rom)


@pytest.fixture
def save(rom: Rom, platform: Platform):
    save = Save(
        rom_id=rom.id,
        file_name="test_save.sav",
        file_name_no_tags="test_save",
        file_extension="sav",
        emulator="test_emulator",
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )
    return dbsaveh.add_save(save)


@pytest.fixture
def state(rom: Rom, platform: Platform):
    state = State(
        rom_id=rom.id,
        file_name="test_state.state",
        file_name_no_tags="test_state",
        file_extension="state",
        emulator="test_emulator",
        file_path=f"{platform.slug}/states/test_emulator",
        file_size_bytes=2.0,
    )
    return dbstateh.add_state(state)


@pytest.fixture
def screenshot(rom: Rom, platform: Platform):
    screenshot = Screenshot(
        rom_id=rom.id,
        file_name="test_screenshot.png",
        file_name_no_tags="test_screenshot",
        file_extension="png",
        file_path=f"{platform.slug}/screenshots",
        file_size_bytes=3.0,
    )
    return dbscreenshotsh.add_screenshot(screenshot)

@pytest.fixture
def admin_user():
    user = User(
        username="test_admin",
        hashed_password=authh.get_password_hash("test_admin_password"),
        role=Role.ADMIN,
    )
    return dbuserh.add_user(user)


@pytest.fixture
def editor_user():
    user = User(
        username="test_editor",
        hashed_password=authh.get_password_hash("test_editor_password"),
        role=Role.EDITOR,
    )
    return dbuserh.add_user(user)


@pytest.fixture
def viewer_user():
    user = User(
        username="test_viewer",
        hashed_password=authh.get_password_hash("test_viewer_password"),
        role=Role.VIEWER,
    )
    return dbuserh.add_user(user)
