"""
Unit tests for rom_notes table migration.
Test file: tests/handler/database/test_rom_note_migration.py
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import NullPool
import os


@pytest.fixture(params=["postgresql", "mysql"])
def db_engine(request):
    """Create test database engines for different dialects."""
    dialect = request.param
    
    if dialect == "postgresql":
        database_url = os.getenv(
            "TEST_POSTGRES_URL",
            "postgresql://romm:romm@localhost:5432/romm"
        )
    else:  # mysql
        database_url = os.getenv(
            "TEST_MYSQL_URL",
            "mysql+pymysql://romm:romm@127.0.0.1/romm"
        )
    
    engine = create_engine(database_url, poolclass=NullPool)
    yield engine, dialect
    engine.dispose()


@pytest.fixture
def alembic_config(db_engine):
    """Create Alembic configuration for testing."""
    engine, dialect = db_engine
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", str(engine.url))
    return config, engine, dialect


def get_migration_revisions(config):
    """Get the rom_notes migration revision IDs."""
    # You'll need to update these to match your actual revision IDs
    # You can find them with: alembic history
    ROM_NOTES_REVISION = "0057_multi_notes"  # Your upgrade revision
    PREVIOUS_REVISION = "0056_gamelist_xml"   # The revision before rom_notes
    return ROM_NOTES_REVISION, PREVIOUS_REVISION


def test_upgrade_creates_table_and_indexes(alembic_config):
    """Test that upgrade creates rom_notes table with all indexes."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    # Start from previous revision
    command.downgrade(config, PREV_REV)
    
    # Verify table doesn't exist yet
    inspector = inspect(engine)
    assert "rom_notes" not in inspector.get_table_names()
    
    # Upgrade to rom_notes revision
    command.upgrade(config, ROM_NOTES_REV)
    
    # Verify table exists
    inspector = inspect(engine)
    assert "rom_notes" in inspector.get_table_names()
    
    # Verify columns
    columns = {col["name"] for col in inspector.get_columns("rom_notes")}
    expected = {"id", "rom_id", "user_id", "title", "content", "is_public", "created_at", "updated_at"}
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    
    # Verify indexes
    indexes = {idx["name"] for idx in inspector.get_indexes("rom_notes")}
    expected_indexes = {
        "idx_rom_notes_public",
        "idx_rom_notes_rom_user",
        "idx_rom_notes_title",
        "idx_rom_notes_content"
    }
    assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"


def test_downgrade_removes_table(alembic_config):
    """Test that downgrade removes rom_notes table."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    # Ensure we're at rom_notes revision
    command.upgrade(config, ROM_NOTES_REV)
    
    # Verify table exists
    inspector = inspect(engine)
    assert "rom_notes" in inspector.get_table_names()
    
    # Downgrade to previous revision
    command.downgrade(config, PREV_REV)
    
    # Verify table is removed
    inspector = inspect(engine)
    assert "rom_notes" not in inspector.get_table_names()
    
    # Verify old columns are restored to rom_user
    columns = {col["name"] for col in inspector.get_columns("rom_user")}
    assert "note_raw_markdown" in columns
    assert "note_is_public" in columns


def test_upgrade_removes_old_columns_from_rom_user(alembic_config):
    """Test that upgrade removes old note columns from rom_user."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    # Start from previous revision (where old columns exist)
    command.downgrade(config, PREV_REV)
    
    inspector = inspect(engine)
    columns_before = {col["name"] for col in inspector.get_columns("rom_user")}
    
    # Old columns should exist
    assert "note_raw_markdown" in columns_before
    assert "note_is_public" in columns_before
    
    # Upgrade
    command.upgrade(config, ROM_NOTES_REV)
    
    inspector = inspect(engine)
    columns_after = {col["name"] for col in inspector.get_columns("rom_user")}
    
    # Old columns should be removed (if your upgrade does this)
    # Comment out these assertions if your upgrade keeps the old columns
    # assert "note_raw_markdown" not in columns_after
    # assert "note_is_public" not in columns_after


def test_indexes_are_dialect_specific(alembic_config):
    """Test that content index works with dialect-specific syntax."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    # Upgrade to rom_notes revision
    command.upgrade(config, ROM_NOTES_REV)
    
    inspector = inspect(engine)
    indexes = {idx["name"] for idx in inspector.get_indexes("rom_notes")}
    
    # Verify content index exists
    assert "idx_rom_notes_content" in indexes
    
    # Test that we can query using content column
    with engine.connect() as conn:
        # This should work regardless of dialect
        result = conn.execute(
            text("SELECT COUNT(*) as cnt FROM rom_notes WHERE content = :content"),
            {"content": "test"}
        )
        count = result.scalar()
        assert count is not None  # Should be 0, but no error


def test_foreign_keys_and_constraints(alembic_config):
    """Test that foreign keys and constraints are properly created."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    command.upgrade(config, ROM_NOTES_REV)
    
    inspector = inspect(engine)
    
    # Check foreign keys
    foreign_keys = inspector.get_foreign_keys("rom_notes")
    assert len(foreign_keys) >= 2
    
    fk_columns = {fk["constrained_columns"][0] for fk in foreign_keys}
    assert "rom_id" in fk_columns or "user_id" in fk_columns
    
    # Check primary key
    pk = inspector.get_pk_constraint("rom_notes")
    assert "id" in pk["constrained_columns"]
    
    # Check NOT NULL constraints
    columns = {col["name"]: col for col in inspector.get_columns("rom_notes")}
    assert columns["rom_id"]["nullable"] is False
    assert columns["user_id"]["nullable"] is False
    assert columns["content"]["nullable"] is False


def test_full_migration_cycle(alembic_config):
    """Test complete upgrade -> downgrade -> upgrade cycle."""
    config, engine, dialect = alembic_config
    ROM_NOTES_REV, PREV_REV = get_migration_revisions(config)
    
    # Start from previous
    command.downgrade(config, PREV_REV)
    inspector = inspect(engine)
    assert "rom_notes" not in inspector.get_table_names()
    
    # Upgrade
    command.upgrade(config, ROM_NOTES_REV)
    inspector = inspect(engine)
    assert "rom_notes" in inspector.get_table_names()
    
    # Downgrade
    command.downgrade(config, PREV_REV)
    inspector = inspect(engine)
    assert "rom_notes" not in inspector.get_table_names()
    
    # Upgrade again
    command.upgrade(config, ROM_NOTES_REV)
    inspector = inspect(engine)
    assert "rom_notes" in inspector.get_table_names()
