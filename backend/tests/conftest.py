import errno
import functools
import hashlib
import os
import re
import socket
import subprocess
import sys
import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import alembic.config
import pytest
from alembic.script import ScriptDirectory
from hypothesis import settings
from joserfc import jwt
from sqlalchemy import (
    Connection,
    Engine,
    create_engine,
    event,
    exists,
    inspect,
    select,
    text,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from tests.factories import (
    make_firmware,
    make_rom,
    make_save,
    make_screenshot,
    make_state,
)

from adapters.services import response_validation
from config import ROMM_DB_DRIVER
from config.config_manager import ConfigManager
from handler.auth.base_handler import auth_handler, oct_key
from handler.auth.constants import ALGORITHM
from handler.database import (
    db_memory_card_handler,
    db_permission_handler,
    db_platform_handler,
    db_rom_handler,
    db_user_handler,
)
from handler.database.base_handler import sync_engine
from logger.formatter import SENSITIVE_KEYS
from models.assets import MemoryCard, MemoryCardVersion, Save, Screenshot, State
from models.audit_event import AuditEvent
from models.client_token import ClientToken
from models.container_adoption import StreamingContainerAdoption
from models.deleted_asset import DeletedAsset
from models.device import Device
from models.device_save_sync import DeviceSaveSync
from models.firmware import Firmware
from models.notification import Notification
from models.notification_channel import NotificationChannel
from models.permission import SystemGroupKey
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

# The test suite talks to nothing but the database; a connection anywhere else
# means a mock was missed. A workstation answers those instantly, a CI runner
# silently drops the packets and the test burns its whole socket timeout (up to
# two minutes for a broker transfer), so refuse them outright.
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _blocked(address: Any) -> bool:
    # Non-tuple addresses are unix sockets, which never leave the machine.
    return isinstance(address, tuple) and address[0] not in _ALLOWED_HOSTS


def _guarded_connect(sock: socket.socket, address: Any) -> None:
    if _blocked(address):
        raise OSError(
            errno.ENETUNREACH, f"outbound network blocked in tests: {address}"
        )
    _real_connect(sock, address)


def _guarded_connect_ex(sock: socket.socket, address: Any) -> int:
    if _blocked(address):
        return errno.ENETUNREACH
    return _real_connect_ex(sock, address)


socket.socket.connect = _guarded_connect  # type: ignore[method-assign,assignment]
socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign,assignment]


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
            found = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not found:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def raise_on_response_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(response_validation, "RAISE_ON_MISMATCH", True)


@pytest.fixture
def lenient(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Production mode: mismatches log to the returned mock instead of raising."""
    log = MagicMock()
    monkeypatch.setattr(response_validation, "RAISE_ON_MISMATCH", False)
    monkeypatch.setattr(response_validation, "_reported", set())
    monkeypatch.setattr(response_validation, "log", log)
    return log


_DEFINER_RE = re.compile(r"\s+DEFINER=\S+")


def _schema_names(conn: Connection, query: str, schema: str) -> Sequence[str]:
    """The first column of `query`, run with `schema` bound to `:s`."""
    return conn.execute(text(query), {"s": schema}).scalars().all()


def _copy_schema(conn: Connection, source: str, target: str) -> None:
    """Copy every table, row, view and trigger of `source` into `target`."""
    objects = conn.execute(
        text(
            "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES"
            " WHERE TABLE_SCHEMA = :s"
        ),
        {"s": source},
    ).all()
    tables = [name for name, kind in objects if kind == "BASE TABLE"]
    views = [name for name, kind in objects if kind == "VIEW"]
    triggers = _schema_names(
        conn,
        "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS"
        " WHERE TRIGGER_SCHEMA = :s ORDER BY EVENT_OBJECT_TABLE, ACTION_ORDER",
        source,
    )
    columns: dict[str, list[str]] = {}
    for table, column in conn.execute(
        text(
            "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS"
            " WHERE TABLE_SCHEMA = :s AND COALESCE(GENERATION_EXPRESSION, '') = ''"
            " ORDER BY ORDINAL_POSITION"
        ),
        {"s": source},
    ):
        columns.setdefault(table, []).append(f"`{column}`")

    # Read the DDL from inside `source`, so views print unqualified table names.
    conn.exec_driver_sql(f"USE `{source}`")
    table_ddl = {
        t: conn.exec_driver_sql(f"SHOW CREATE TABLE `{t}`").one()[1] for t in tables
    }
    view_ddl = [
        _DEFINER_RE.sub(
            "", conn.exec_driver_sql(f"SHOW CREATE VIEW `{v}`").one()[1], count=1
        )
        for v in views
    ]
    trigger_ddl = [
        _DEFINER_RE.sub(
            "", conn.exec_driver_sql(f"SHOW CREATE TRIGGER `{t}`").one()[2], count=1
        )
        for t in triggers
    ]
    conn.exec_driver_sql(f"USE `{target}`")

    def copy_table(table: str, ddl: str) -> None:
        conn.exec_driver_sql(ddl)
        cols = ", ".join(columns[table])
        conn.exec_driver_sql(
            f"INSERT INTO `{table}` ({cols}) SELECT {cols} FROM `{source}`.`{table}`"
        )

    # The version row goes in last, so a copy cut short reads as unmigrated.
    version_ddl = table_ddl.pop("alembic_version")
    conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
    for table, ddl in table_ddl.items():
        copy_table(table, ddl)
    conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")
    # A view can select from another view, so retry until each finds its sources.
    pending = view_ddl
    while pending:
        failed = []
        for ddl in pending:
            try:
                conn.exec_driver_sql(ddl)
            except DBAPIError:
                failed.append(ddl)
        if len(failed) == len(pending):
            conn.exec_driver_sql(failed[0])
        pending = failed
    for ddl in trigger_ddl:
        conn.exec_driver_sql(ddl)
    copy_table("alembic_version", version_ddl)
    conn.commit()


def _alembic_version(conn: Connection, schema: str) -> str | None:
    if not inspect(conn).has_table("alembic_version", schema=schema):
        return None
    return conn.exec_driver_sql(
        f"SELECT version_num FROM `{schema}`.alembic_version"
    ).scalar()


def _recreate_database(conn: Connection, name: str) -> None:
    conn.exec_driver_sql(f"DROP DATABASE IF EXISTS `{name}`")
    conn.exec_driver_sql(f"CREATE DATABASE `{name}`")


def _migrations_digest() -> str:
    """Hash the migrations and the models and utils they import, so an edit rebuilds the template."""
    digest = hashlib.sha256()
    for path in sorted(
        path
        for root in ("alembic", "models", "utils")
        for path in Path(root).rglob("*.py")
    ):
        digest.update(str(path).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:12]


@contextmanager
def _server_lock(conn: Connection, name: str) -> Iterator[bool]:
    """Hold the MariaDB named lock `name`, yielding whether it was acquired."""
    lock = {"name": name}
    acquired = conn.execute(text("SELECT GET_LOCK(:name, 1800)"), lock).scalar() == 1
    try:
        yield acquired
    finally:
        if acquired:
            conn.execute(text("SELECT RELEASE_LOCK(:name)"), lock)


def _build_template(conn: Connection, prefix: str, template: str) -> None:
    """Migrate `template` from scratch, dropping every other `prefix` template first."""
    schemas: Sequence[str] = (
        conn.execute(text("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA"))
        .scalars()
        .all()
    )
    for name in schemas:
        if name == prefix or name.startswith(f"{prefix}_"):
            conn.exec_driver_sql(f"DROP DATABASE `{name}`")
    _recreate_database(conn, template)
    # The app's engine binds DB_NAME at import, hence a subprocess.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=os.environ | {"DB_NAME": template},
        check=True,
    )


def _clone_template_into_fresh_database() -> None:
    """Fill an empty xdist worker database from a template migrated once under a server lock."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker or ROMM_DB_DRIVER not in ("mariadb", "mysql"):
        return
    url = ConfigManager.get_db_engine()
    if not url.database:
        return
    prefix = f"{url.database.removesuffix(f'_{worker}')}_template"

    worker_engine = create_engine(url)
    try:
        with worker_engine.connect() as conn:
            if _alembic_version(conn, url.database):
                return
            # Without a version row, any tables are a clone that was cut short.
            _recreate_database(conn, url.database)
            template = f"{prefix}_{_migrations_digest()}"
            head = ScriptDirectory.from_config(
                alembic.config.Config("alembic.ini")
            ).get_current_head()
            with _server_lock(conn, prefix) as acquired:
                if not acquired:
                    return
                if _alembic_version(conn, template) != head:
                    _build_template(conn, prefix, template)
                try:
                    _copy_schema(conn, template, url.database)
                except DBAPIError as exc:
                    warnings.warn(
                        f"Template clone failed, migrating from scratch: {exc}",
                        stacklevel=1,
                    )
                    # Leave alembic an empty database to migrate.
                    _recreate_database(conn, url.database)
    finally:
        worker_engine.dispose()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # The slow migration tests go first so they overlap the rest of the suite.
    items.sort(key=lambda item: item.path.name != "test_migrations.py")


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    _ensure_database_exists()
    _clone_template_into_fresh_database()
    alembic.config.main(argv=["upgrade", "head"])


# Children before parents. Deleting a parent cascades to the tables not listed.
_CLEARED_MODELS = (
    AuditEvent,
    Notification,
    NotificationChannel,
    PlaySession,
    ClientToken,
    SyncSession,
    DeviceSaveSync,
    Device,
    MemoryCardVersion,
    MemoryCard,
    StreamingContainerAdoption,
    DeletedAsset,
    Save,
    State,
    Screenshot,
    RomFile,
    Rom,
    Firmware,
    Platform,
    User,
)
# One round trip finds the tables holding rows, so empty ones skip their DELETE.
_HAS_ROWS = select(
    *(
        exists().select_from(model).label(model.__tablename__)
        for model in _CLEARED_MODELS
    )
)


def _clear_tables() -> None:
    with session.begin() as s:
        has_rows = s.execute(_HAS_ROWS).one()
        for model, dirty in zip(_CLEARED_MODELS, has_rows, strict=True):
            if dirty:
                s.query(model).delete(synchronize_session=False)


@pytest.fixture(autouse=True)
def clear_database():
    _clear_tables()
    # Drop any cached gallery filter values to keep tests isolated.
    db_rom_handler.invalidate_filter_values_cache()


@contextmanager
def _capture_statements(target: Engine) -> Iterator[list[str]]:
    """Every statement `target` runs inside the block."""
    statements: list[str] = []

    def before_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(target, "before_cursor_execute", before_execute)
    try:
        yield statements
    finally:
        event.remove(target, "before_cursor_execute", before_execute)


@pytest.fixture
def executed_statements() -> Iterator[list[str]]:
    """Every statement the sync engine runs while the fixture is active."""
    with _capture_statements(sync_engine) as statements:
        yield statements


_VCR_REDACTED = "x" * 30

# The lookbehind stops RetroAchievements' `y` key matching inside `display=`.
_BODY_SECRET_RE = re.compile(
    rf"(?<![A-Za-z_-])({'|'.join(re.escape(k) for k in SENSITIVE_KEYS)})=[^&\s\"\\]*".encode(),
    re.IGNORECASE,
)


def _scrub_response_body(response: dict[str, Any]) -> dict[str, Any]:
    """Mask credentials that providers echo back inside response bodies."""
    body = response.get("body", {}).get("string")
    if isinstance(body, str):
        body = body.encode()
    if body:
        response["body"]["string"] = _BODY_SECRET_RE.sub(
            rf"\1={_VCR_REDACTED}".encode(), body
        )
    return response


@pytest.fixture(scope="module")
def vcr_config():
    """Fixture to configure VCR.py settings."""
    return {
        # Default `match_on`, plus raw_body.
        "match_on": ["method", "scheme", "host", "port", "path", "query", "raw_body"],
        "filter_headers": [(k, _VCR_REDACTED) for k in sorted(SENSITIVE_KEYS)],
        "filter_query_parameters": [(k, _VCR_REDACTED) for k in sorted(SENSITIVE_KEYS)],
        "before_record_response": _scrub_response_body,
    }


@pytest.fixture
def platform():
    platform = Platform(
        name="test_platform", slug="test_platform_slug", fs_slug="test_platform_slug"
    )
    return db_platform_handler.add_platform(platform)


@pytest.fixture
def other_platform():
    platform = Platform(name="other", slug="other_slug", fs_slug="other_slug")
    return db_platform_handler.add_platform(platform)


@pytest.fixture
def firmware(platform: Platform):
    """Firmware whose file is still on disk."""
    return make_firmware(platform, "present.bin")


@pytest.fixture
def missing_firmware(platform: Platform):
    """Firmware flagged by a scan as gone from the filesystem."""
    return make_firmware(platform, "gone.bin", missing=True)


@pytest.fixture
def rom(admin_user: User, platform: Platform):
    rom = make_rom(platform, "test_rom", slug="test_rom_slug")
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)

    return rom


@pytest.fixture
def second_rom(admin_user: User, platform: Platform):
    """A second ROM on the same platform, for tests that scope by ROM."""
    rom = make_rom(platform, "test_rom_2", slug="test_rom_slug_2")
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
    rom = make_rom(
        platform,
        "test_multi_file_rom",
        fs_extension="",
        slug="test_multi_file_rom_slug",
    )
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
    return make_save(
        rom,
        admin_user,
        "test_save.sav",
        emulator="test_emulator",
        slot="autosave",
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )


@pytest.fixture
def second_save(second_rom: Rom, platform: Platform, admin_user: User):
    """Slot-bound save on `second_rom`, to check ROM-scoped queries exclude it."""
    return make_save(
        second_rom,
        admin_user,
        "test_save_2.sav",
        emulator="test_emulator",
        slot="autosave",
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )


@pytest.fixture
def archival_save(rom: Rom, platform: Platform, admin_user: User):
    """Null-slot save representing a web-UI / archival upload.

    These should never appear in negotiate plans.
    """
    return make_save(
        rom,
        admin_user,
        "archival.sav",
        emulator="test_emulator",
        slot=None,
        file_path=f"{platform.slug}/saves/test_emulator",
        file_size_bytes=1.0,
    )


@pytest.fixture
def state(rom: Rom, platform: Platform, admin_user: User):
    return make_state(
        rom,
        admin_user,
        "test_state.state",
        emulator="test_emulator",
        file_path=f"{platform.slug}/states/test_emulator",
        file_size_bytes=2.0,
    )


@pytest.fixture
def second_state(second_rom: Rom, platform: Platform, admin_user: User):
    """State on `second_rom`, to check ROM-scoped queries exclude it."""
    return make_state(
        second_rom,
        admin_user,
        "test_state_2.state",
        emulator="test_emulator",
        file_path=f"{platform.slug}/states/test_emulator",
        file_size_bytes=2.0,
    )


@pytest.fixture
def screenshot(rom: Rom, platform: Platform, admin_user: User):
    return make_screenshot(
        rom,
        admin_user,
        "test_screenshot.png",
        file_size_bytes=3.0,
    )


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


@functools.cache
def _password_hash(password: str) -> str:
    """Memoized: bcrypt costs a quarter-second and the user fixtures below hash
    the same three passwords for well over a thousand tests."""
    return auth_handler.get_password_hash(password)


@pytest.fixture
def admin_user():
    user = User(
        username="test_admin",
        hashed_password=_password_hash("test_admin_password"),
        role=Role.ADMIN,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def editor_user():
    # role collapses to `user`; editor-level access now comes from the group.
    group = db_permission_handler.get_system_group(SystemGroupKey.EDITOR)
    user = User(
        username="test_editor",
        hashed_password=_password_hash("test_editor_password"),
        role=Role.USER,
        permission_group_id=group.id if group else None,
    )
    return db_user_handler.add_user(user)


@pytest.fixture
def viewer_user():
    group = db_permission_handler.get_system_group(SystemGroupKey.VIEWER)
    user = User(
        username="test_viewer",
        hashed_password=_password_hash("test_viewer_password"),
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
