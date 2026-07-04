import importlib.util
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine

from config import ROMM_DB_DRIVER
from config.config_manager import ConfigManager
from utils.database import CustomJSON


def _load_migration() -> ModuleType:
    migration_path = Path(__file__).parents[1] / "alembic/versions/1.8_.py"
    spec = importlib.util.spec_from_file_location("migration_1_8", migration_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration_1_8 = _load_migration()


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    url = ConfigManager.get_db_engine()
    assert url.database

    db_name = f"{url.database}_migration_{uuid.uuid4().hex[:8]}"
    assert re.fullmatch(r"[A-Za-z0-9_]+", db_name)

    if ROMM_DB_DRIVER in ("mariadb", "mysql"):
        admin_engine = create_engine(url.set(database="information_schema"))
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE `{db_name}`"))

        engine = create_engine(url.set(database=db_name))
        try:
            yield engine
        finally:
            engine.dispose()
            with admin_engine.begin() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS `{db_name}`"))
            admin_engine.dispose()
    elif ROMM_DB_DRIVER == "postgresql":
        admin_engine = create_engine(
            url.set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))

        engine = create_engine(url.set(database=db_name))
        try:
            yield engine
        finally:
            engine.dispose()
            with admin_engine.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
            admin_engine.dispose()
    else:
        pytest.fail(f"Unsupported database driver: {ROMM_DB_DRIVER}")


def _run_1_8_upgrade(conn: Connection) -> None:
    context = MigrationContext.configure(conn, opts={"render_as_batch": True})
    previous_op = getattr(migration_1_8, "op")
    setattr(migration_1_8, "op", Operations(context))
    try:
        getattr(migration_1_8, "upgrade")()
    finally:
        setattr(migration_1_8, "op", previous_op)


def _columns(conn: Connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(conn).get_columns(table_name)}


def _has_table(conn: Connection, table_name: str) -> bool:
    return inspect(conn).has_table(table_name)


def _count(conn: Connection, table_name: str) -> int:
    table = sa.table(table_name)
    return int(conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())


def _create_legacy_platforms(
    conn: Connection, table_name: str = "platforms"
) -> sa.Table:
    table = sa.Table(
        table_name,
        sa.MetaData(),
        sa.Column("igdb_id", sa.String(length=10), nullable=True),
        sa.Column("sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=400), nullable=True),
        sa.Column("logo_path", sa.String(length=1000), nullable=True),
        sa.Column("n_roms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("slug"),
    )
    table.create(conn)
    return table


def _create_final_platforms(conn: Connection) -> sa.Table:
    table = sa.Table(
        "platforms",
        sa.MetaData(),
        sa.Column("igdb_id", sa.String(length=10), nullable=True),
        sa.Column("sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("fs_slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=400), nullable=True),
        sa.Column("logo_path", sa.String(length=1000), nullable=True),
        sa.Column("n_roms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("fs_slug"),
    )
    table.create(conn)
    return table


def _create_legacy_roms(conn: Connection) -> sa.Table:
    table = sa.Table(
        "roms",
        sa.MetaData(),
        sa.Column("r_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("r_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_slug", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=True),
        sa.Column("file_extension", sa.String(length=10), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Float(), nullable=True),
        sa.Column("file_size_units", sa.String(length=10), nullable=True),
        sa.Column("name", sa.String(length=350), nullable=True),
        sa.Column("r_slug", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("path_cover_s", sa.Text(), nullable=True),
        sa.Column("path_cover_l", sa.Text(), nullable=True),
        sa.Column("has_cover", sa.Boolean(), nullable=True),
        sa.Column("region", sa.String(length=20), nullable=True),
        sa.Column("revision", sa.String(length=20), nullable=True),
        sa.Column("tags", CustomJSON(), nullable=True),
        sa.Column("multi", sa.Boolean(), nullable=True),
        sa.Column("files", CustomJSON(), nullable=True),
        sa.PrimaryKeyConstraint("p_slug", "file_name"),
    )
    table.create(conn)
    return table


def _create_preswap_roms(conn: Connection, table_name: str = "roms") -> sa.Table:
    table = sa.Table(
        table_name,
        sa.MetaData(),
        sa.Column("r_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("r_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_slug", sa.String(length=50), nullable=False),
        sa.Column("p_name", sa.String(length=150), nullable=True),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=True),
        sa.Column("file_extension", sa.String(length=10), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Float(), nullable=True),
        sa.Column("file_size_units", sa.String(length=10), nullable=True),
        sa.Column("r_name", sa.String(length=150), nullable=True),
        sa.Column("r_slug", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("path_cover_s", sa.Text(), nullable=True),
        sa.Column("path_cover_l", sa.Text(), nullable=True),
        sa.Column("has_cover", sa.Boolean(), nullable=True),
        sa.Column("region", sa.String(length=20), nullable=True),
        sa.Column("revision", sa.String(length=20), nullable=True),
        sa.Column("tags", CustomJSON(), nullable=True),
        sa.Column("multi", sa.Boolean(), nullable=True),
        sa.Column("files", CustomJSON(), nullable=True),
        sa.Column("url_cover", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("p_slug", "file_name"),
    )
    table.create(conn)
    return table


def _create_final_roms(conn: Connection) -> sa.Table:
    table = sa.Table(
        "roms",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), autoincrement=True),
        sa.Column("r_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_igdb_id", sa.String(length=10), nullable=True),
        sa.Column("r_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("p_slug", sa.String(length=50), nullable=False),
        sa.Column("p_name", sa.String(length=150), nullable=True),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=10), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Float(), nullable=True),
        sa.Column("file_size_units", sa.String(length=10), nullable=True),
        sa.Column("r_name", sa.String(length=350), nullable=True),
        sa.Column("r_slug", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("path_cover_s", sa.Text(), nullable=True),
        sa.Column("path_cover_l", sa.Text(), nullable=True),
        sa.Column("has_cover", sa.Boolean(), nullable=True),
        sa.Column("region", sa.String(length=20), nullable=True),
        sa.Column("revision", sa.String(length=20), nullable=True),
        sa.Column("tags", CustomJSON(), nullable=True),
        sa.Column("multi", sa.Boolean(), nullable=True),
        sa.Column("files", CustomJSON(), nullable=True),
        sa.Column("url_cover", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    table.create(conn)
    return table


def _insert_platform(table: sa.Table, conn: Connection, slug: str) -> None:
    values = {
        "igdb_id": "1",
        "sgdb_id": "2",
        "slug": slug,
        "name": slug.upper(),
        "logo_path": None,
        "n_roms": 1,
    }
    if "fs_slug" in table.c:
        values["fs_slug"] = slug

    conn.execute(table.insert().values(values))


def _rom_values(file_name: str, r_name: str) -> dict[str, object]:
    return {
        "r_igdb_id": "1",
        "p_igdb_id": "2",
        "r_sgdb_id": "3",
        "p_sgdb_id": "4",
        "p_slug": "snes",
        "p_name": "SNES",
        "file_name": file_name,
        "file_name_no_tags": file_name,
        "file_extension": "zip",
        "file_path": "snes/roms",
        "file_size": 1.0,
        "file_size_units": "MB",
        "r_name": r_name,
        "r_slug": r_name.lower(),
        "summary": None,
        "path_cover_s": None,
        "path_cover_l": None,
        "has_cover": False,
        "region": "USA",
        "revision": None,
        "tags": [],
        "multi": False,
        "files": [],
        "url_cover": None,
    }


def _insert_legacy_rom(table: sa.Table, conn: Connection) -> None:
    values = _rom_values("sonic.zip", "Sonic")
    values["name"] = values.pop("r_name")
    values.pop("p_name")
    values.pop("url_cover")
    conn.execute(table.insert().values(values))


def _insert_rom(table: sa.Table, conn: Connection, file_name: str, r_name: str) -> None:
    values = _rom_values(file_name, r_name)
    conn.execute(table.insert().values(values))


def test_1_8_upgrade_runs_from_1_7_schema(migration_engine: Engine):
    with migration_engine.begin() as conn:
        platforms = _create_legacy_platforms(conn)
        roms = _create_legacy_roms(conn)
        _insert_platform(platforms, conn, "snes")
        _insert_legacy_rom(roms, conn)

        _run_1_8_upgrade(conn)

        assert not _has_table(conn, "old_platforms")
        assert not _has_table(conn, "old_roms")
        assert "fs_slug" in _columns(conn, "platforms")
        assert "id" in _columns(conn, "roms")
        assert "r_name" in _columns(conn, "roms")
        assert "name" not in _columns(conn, "roms")
        assert (
            conn.execute(text("SELECT fs_slug FROM platforms")).scalar_one() == "snes"
        )
        assert conn.execute(text("SELECT r_name FROM roms")).scalar_one() == "Sonic"


def test_1_8_upgrade_reenters_after_rom_name_rename(migration_engine: Engine):
    with migration_engine.begin() as conn:
        platforms = _create_final_platforms(conn)
        roms = _create_preswap_roms(conn)
        _insert_platform(platforms, conn, "snes")
        _insert_rom(roms, conn, "sonic.zip", "Sonic")

        _run_1_8_upgrade(conn)

        assert not _has_table(conn, "old_roms")
        assert "id" in _columns(conn, "roms")
        assert "name" not in _columns(conn, "roms")
        assert conn.execute(text("SELECT r_name FROM roms")).scalar_one() == "Sonic"


def test_1_8_upgrade_reenters_mid_roms_swap(migration_engine: Engine):
    with migration_engine.begin() as conn:
        platforms = _create_final_platforms(conn)
        old_roms = _create_preswap_roms(conn, "old_roms")
        roms = _create_final_roms(conn)
        _insert_platform(platforms, conn, "snes")
        _insert_rom(old_roms, conn, "sonic.zip", "Sonic")
        _insert_rom(old_roms, conn, "mario.zip", "Mario")
        _insert_rom(roms, conn, "sonic.zip", "Sonic")

        _run_1_8_upgrade(conn)

        assert not _has_table(conn, "old_roms")
        assert _count(conn, "roms") == 2
        assert {
            row.file_name
            for row in conn.execute(text("SELECT file_name FROM roms")).fetchall()
        } == {"sonic.zip", "mario.zip"}


def test_1_8_upgrade_reenters_mid_platforms_swap(migration_engine: Engine):
    with migration_engine.begin() as conn:
        old_platforms = _create_legacy_platforms(conn, "old_platforms")
        platforms = _create_final_platforms(conn)
        roms = _create_final_roms(conn)
        _insert_platform(old_platforms, conn, "snes")
        _insert_platform(old_platforms, conn, "gba")
        _insert_platform(platforms, conn, "snes")
        _insert_rom(roms, conn, "sonic.zip", "Sonic")

        _run_1_8_upgrade(conn)

        assert not _has_table(conn, "old_platforms")
        assert _count(conn, "platforms") == 2
        assert {
            row.fs_slug
            for row in conn.execute(text("SELECT fs_slug FROM platforms")).fetchall()
        } == {"snes", "gba"}


def test_1_8_upgrade_is_idempotent_after_completion(migration_engine: Engine):
    with migration_engine.begin() as conn:
        platforms = _create_final_platforms(conn)
        roms = _create_final_roms(conn)
        _insert_platform(platforms, conn, "snes")
        _insert_rom(roms, conn, "sonic.zip", "Sonic")

        _run_1_8_upgrade(conn)
        _run_1_8_upgrade(conn)

        assert not _has_table(conn, "old_platforms")
        assert not _has_table(conn, "old_roms")
        assert _count(conn, "platforms") == 1
        assert _count(conn, "roms") == 1
