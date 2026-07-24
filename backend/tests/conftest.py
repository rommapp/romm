import os
import re
from datetime import datetime, timedelta, timezone

import alembic.config
import pytest
from hypothesis import settings
from joserfc import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import ROMM_DB_DRIVER
from config.config_manager import ConfigManager
from handler.auth import auth_handler
from handler.auth.base_handler import ALGORITHM, oct_key
from handler.database import (
    db_memory_card_handler,
    db_permission_handler,
    db_platform_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from models.assets import MemoryCard, MemoryCardVersion, Save, Screenshot, State
from models.client_token import ClientToken
from models.container_adoption import StreamingContainerAdoption
from models.device import Device
from models.device_save_sync import DeviceSaveSync
from models.platform import Platform
from models.play_session import PlaySession
from models.rom import Rom, RomFile
from models.sync_session import SyncSession
from models.user import Role, User

engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
session = sessionmaker(bind=engine, expire_on_commit=False)

settings.register_profile("ci", max_examples=200, deadline=None)
settings.register_profile("dev", max_examples=50, deadline=None)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))


def _ensure_database_exists() -> None:
    """Create the (possibly per-xdist-worker) test database if it's missing.

    The base `romm_test` database is provisioned by CI / local setup, but the
    per-worker databases used under pytest-xdist (`romm_test_gw0`, ...) are
    created on demand here, just before migrations run.
    """
    url = ConfigManager.get_db_engine()
    db_name = url.database
    if not db_name:
        return

    # The name is interpolated into a CREATE DATABASE statement below;
    # identifiers can't be passed as bind parameters, so validate it up-front
    # rather than rely on quoting. Test databases are always plain identifiers
    # (`romm_test`, `romm_test_gw0`, ...).
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise ValueError(f"Refusing to create database with unsafe name: {db_name!r}")

    if ROMM_DB_DRIVER in ("mariadb", "mysql"):
        # Connect to a maintenance schema that always exists; CREATE DATABASE is
        # a server-level command regardless of the connected schema.
        admin_engine = create_engine(url.set(database="information_schema"))
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
        admin_engine.dispose()
    elif ROMM_DB_DRIVER == "postgresql":
        # CREATE DATABASE can't run inside a transaction.
        admin_engine = create_engine(
            url.set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    _ensure_database_exists()
    alembic.config.main(argv=["upgrade", "head"])


@pytest.fixture(autouse=True)
def clear_database():
    with session.begin() as s:
        s.query(PlaySession).delete(synchronize_session="evaluate")
        s.query(ClientToken).delete(synchronize_session="evaluate")
        s.query(SyncSession).delete(synchronize_session="evaluate")
        s.query(DeviceSaveSync).delete(synchronize_session="evaluate")
        s.query(Device).delete(synchronize_session="evaluate")
        s.query(MemoryCardVersion).delete(synchronize_session="evaluate")
        s.query(MemoryCard).delete(synchronize_session="evaluate")
        s.query(StreamingContainerAdoption).delete(synchronize_session="evaluate")
        s.query(Save).delete(synchronize_session="evaluate")
        s.query(State).delete(synchronize_session="evaluate")
        s.query(Screenshot).delete(synchronize_session="evaluate")
        s.query(RomFile).delete(synchronize_session="evaluate")
        s.query(Rom).delete(synchronize_session="evaluate")
        s.query(Platform).delete(synchronize_session="evaluate")
        s.query(User).delete(synchronize_session="evaluate")

    # Drop any cached gallery filter values to keep tests isolated.
    db_rom_handler.invalidate_filter_values_cache()


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
def rom_file(rom: Rom):
    """A single content file attached to the `rom` fixture."""
    rom_file = RomFile(
        rom_id=rom.id,
        file_name="test_rom.zip",
        file_path=rom.fs_path,
        file_size_bytes=1000,
    )
    return db_rom_handler.add_rom_file(rom_file)


@pytest.fixture
def multi_file_rom(admin_user: User, platform: Platform):
    """A ROM stored as a game folder with multiple files (e.g. multi-disc).

    Exercises the multi-file download path, where each entry's download name is
    derived from `file.rom.full_path` — the back-reference that must remain
    usable after the handler session closes.
    """
    rom = Rom(
        platform_id=platform.id,
        name="test_multi_file_rom",
        slug="test_multi_file_rom_slug",
        fs_name="test_multi_file_rom",
        fs_name_no_tags="test_multi_file_rom",
        fs_name_no_ext="test_multi_file_rom",
        fs_extension="",
        fs_path=f"{platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

    folder_path = f"{rom.fs_path}/{rom.fs_name}"
    for file_name in ("disc1.bin", "disc2.bin"):
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=folder_path,
                file_size_bytes=1,
            )
        )

    return db_rom_handler.get_rom(rom.id)


@pytest.fixture
def save(rom: Rom, platform: Platform, admin_user: User):
    """Slot-bound save (the canonical device-uploaded shape).

    Sync negotiation only considers saves with a non-null slot — null-slot
    saves are treated as web-UI / archival backups. Tests that need to
    represent an archival save should use the `archival_save` fixture.
    """
    save = Save(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="test_save.sav",
        file_name_no_tags="test_save",
        file_name_no_ext="test_save",
        file_extension="sav",
        emulator="test_emulator",
        slot="autosave",
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )
    return db_save_handler.add_save(save)


@pytest.fixture
def archival_save(rom: Rom, platform: Platform, admin_user: User):
    """Null-slot save representing a web-UI / archival upload.

    These should never appear in negotiate plans.
    """
    save = Save(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="archival.sav",
        file_name_no_tags="archival",
        file_name_no_ext="archival",
        file_extension="sav",
        emulator="test_emulator",
        slot=None,
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
def memory_card(admin_user: User, platform: Platform):
    """A private PCSX2 memory card owned by the admin user, no versions yet."""
    card = MemoryCard(
        user_id=admin_user.id,
        emulator="pcsx2",
        platform_id=platform.id,
        name="test_card",
        slot=1,
        is_public=False,
    )
    return db_memory_card_handler.add_card(card)


@pytest.fixture
def memory_card_version(memory_card: MemoryCard, platform: Platform):
    """A single snapshot attached to the `memory_card` fixture."""
    version = MemoryCardVersion(
        memory_card_id=memory_card.id,
        file_name="test_card.zip",
        file_name_no_tags="test_card",
        file_name_no_ext="test_card",
        file_extension="zip",
        file_path=f"{platform.slug}/memory_cards/pcsx2",
        file_size_bytes=4.0,
        content_hash="0123456789abcdef0123456789abcdef",
    )
    return db_memory_card_handler.add_version(version)


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
    # role collapses to `user`; editor-level access now comes from the group.
    group = db_permission_handler.get_group_by_name("Editor (legacy)")
    user = User(
        username="test_editor",
        hashed_password=auth_handler.get_password_hash("test_editor_password"),
        role=Role.USER,
        permission_group_id=group.id if group else None,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def viewer_user():
    group = db_permission_handler.get_group_by_name("Viewer (legacy)")
    user = User(
        username="test_viewer",
        hashed_password=auth_handler.get_password_hash("test_viewer_password"),
        role=Role.USER,
        permission_group_id=group.id if group else None,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def expired_refresh_token(admin_user: User) -> str:
    expire = int((datetime.now(timezone.utc) + timedelta(seconds=-1)).timestamp())

    return jwt.encode(
        {"alg": ALGORITHM},
        {
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
            "type": "refresh",
            "jti": "expired-test-jti",
            "exp": expire,
        },
        oct_key,
    )
