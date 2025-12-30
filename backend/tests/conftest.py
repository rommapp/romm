import os
import shutil
from pathlib import Path

import alembic.config
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.config_manager import ConfigManager
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

engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
session = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_database(request):
    original_cwd = os.getcwd()
    try:
        os.chdir(
            os.path.join(os.path.dirname(__file__), "..")
        )  # Change to backend directory
        alembic.config.main(argv=["-c", "alembic.ini", "upgrade", "head"])
    finally:
        os.chdir(original_cwd)  # Restore original cwd

    # Setup dummy library files for tests
    library_base_path = Path(os.getcwd()) / "romm_test" / "library"

    # Create necessary directories
    (library_base_path / "n64" / "roms").mkdir(parents=True, exist_ok=True)
    (library_base_path / "psx" / "roms").mkdir(parents=True, exist_ok=True)
    (library_base_path / "n64" / "roms" / "Super Mario 64 (J) (Rev A)").mkdir(
        parents=True, exist_ok=True
    )
    (library_base_path / "n64" / "roms" / "Test Multi Rom [USA]").mkdir(
        parents=True, exist_ok=True
    )
    (library_base_path / "n64" / "roms" / "Sonic (EU) [T]" / "translation").mkdir(
        parents=True, exist_ok=True
    )

    # Create dummy files
    (library_base_path / "n64" / "roms" / "Paper Mario (USA).z64").write_bytes(
        b"Paper Mario content"
    )
    (
        library_base_path / "n64" / "roms" / "Zelda (USA) (Rev 1) [En,Fr] [Test].n64"
    ).write_bytes(b"Zelda content")
    (library_base_path / "n64" / "roms" / "test_game.n64").write_bytes(b"Test N64 ROM")
    (library_base_path / "n64" / "roms" / "hash_test.n64").write_bytes(
        b"Test ROM content for hashing"
    )
    (library_base_path / "n64" / "roms" / "excluded_test.tmp").write_bytes(
        b"Excluded content"
    )
    (library_base_path / "psx" / "roms" / "PaRappa the Rapper.zip").write_bytes(
        b"Zip content"
    )
    (
        library_base_path
        / "n64"
        / "roms"
        / "Super Mario 64 (J) (Rev A)"
        / "Super Mario 64 (J) (Rev A) [Part 1].z64"
    ).write_bytes(b"Part 1 content")
    (
        library_base_path
        / "n64"
        / "roms"
        / "Super Mario 64 (J) (Rev A)"
        / "Super Mario 64 (J) (Rev A) [Part 2].z64"
    ).write_bytes(b"Part 2 content")
    (
        library_base_path / "n64" / "roms" / "Sonic (EU) [T]" / "Sonic (EU) [T].n64"
    ).write_bytes(b"Sonic content")
    (
        library_base_path
        / "n64"
        / "roms"
        / "Sonic (EU) [T]"
        / "translation"
        / "Sonic (EU) [T-En].z64"
    ).write_bytes(b"Sonic translation content")

    # Clean up dummy files after tests are done
    def teardown_dummy_files():
        shutil.rmtree(library_base_path, ignore_errors=True)

    request.addfinalizer(teardown_dummy_files)


@pytest.fixture(autouse=True)
def clear_database():
    with session.begin() as s:
        s.query(Save).delete(synchronize_session="evaluate")
        s.query(State).delete(synchronize_session="evaluate")
        s.query(Screenshot).delete(synchronize_session="evaluate")
        s.query(Rom).delete(synchronize_session="evaluate")
        s.query(Platform).delete(synchronize_session="evaluate")
        s.query(User).delete(synchronize_session="evaluate")


@pytest.fixture(scope="module")
def vcr_config():
    """Fixture to configure VCR.py settings."""
    return {
        # Default `match_on`, plus raw_body.
        "match_on": ["method", "scheme", "host", "port", "path", "query", "raw_body"],
    }


@pytest.fixture
def platform():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    return db_platform_handler.add_platform(platform)


@pytest.fixture
def rom(admin_user: User, platform: Platform):
    rom = Rom(
        platform_id=platform.id,
        name="test_rom",
        slug="test_rom_slug",
        fs_name="test_rom.zip",
        fs_name_no_tags="test_rom",
        fs_name_no_ext="test_rom",
        fs_extension="zip",
        fs_path=f"{platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)

    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

    return rom


@pytest.fixture
def save(rom: Rom, platform: Platform, admin_user: User):
    save = Save(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="test_save.sav",
        file_name_no_tags="test_save",
        file_name_no_ext="test_save",
        file_extension="sav",
        emulator="test_emulator",
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )
    return db_save_handler.add_save(save)


@pytest.fixture
def state(rom: Rom, platform: Platform, admin_user: User):
    state = State(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="test_state.state",
        file_name_no_tags="test_state",
        file_name_no_ext="test_state",
        file_extension="state",
        emulator="test_emulator",
        file_path=f"{platform.slug}/states/test_emulator",
        file_size_bytes=2.0,
    )
    return db_state_handler.add_state(state)


@pytest.fixture
def screenshot(rom: Rom, platform: Platform, admin_user: User):
    screenshot = Screenshot(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="test_screenshot.png",
        file_name_no_tags="test_screenshot",
        file_name_no_ext="test_screenshot",
        file_extension="png",
        file_path=f"{platform.slug}/screenshots",
        file_size_bytes=3.0,
    )
    return db_screenshot_handler.add_screenshot(screenshot)


@pytest.fixture
def admin_user():
    user = User(
        username="test_admin",
        hashed_password=auth_handler.get_password_hash("test_admin_password"),
        role=Role.ADMIN,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def editor_user():
    user = User(
        username="test_editor",
        hashed_password=auth_handler.get_password_hash("test_editor_password"),
        role=Role.EDITOR,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def viewer_user():
    user = User(
        username="test_viewer",
        hashed_password=auth_handler.get_password_hash("test_viewer_password"),
        role=Role.VIEWER,
    )
    return db_user_handler.add_user(user)
