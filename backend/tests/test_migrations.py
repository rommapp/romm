"""Guard the models against drifting away from the migrated schema.

The test database is built from the migrations, so an index declared in one but
not the other goes unnoticed until autogenerate proposes dropping it.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects import mysql, postgresql

import models
from handler.database import db_rom_handler
from handler.database.base_handler import sync_engine
from models.base import BaseModel
from models.rom import FULL_PATH_HASH_LENGTH, Rom, compute_full_path_hash
from utils.database import (
    AUTOGENERATE_EXEMPT_INDEX_NAMES,
    POSTGRESQL_FK_INDEXES,
    full_path_digest_sql,
    has_column,
    is_postgresql,
)

# `compare_metadata` yields flat tuples for schema-level diffs, and a list of
# tuples for column-level ones. Only these two name an index.
INDEX_DIFF_OPS = frozenset({"add_index", "remove_index"})

# The revision that owns each model-declared generated column's DDL. The model
# and the revision hold the same SQL on purpose, since a revision that imported
# its DDL from the model would rewrite itself the day the expression changed, so
# the pairing is pinned here and checked below.
GENERATED_COLUMN_REVISIONS = {
    "generated_primary_region": "0108_roms_primary_region.py",
    "generated_hltb_main_story": "0128_hltb_main_story_column.py",
}


def _leading_columns(table: Table) -> set[str]:
    """Names of the columns a lookup on this table can start from."""
    groups = [list(table.primary_key.columns)]
    groups += [list(index.columns) for index in table.indexes]
    groups += [
        list(constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    return {columns[0].name for columns in groups if columns}


def test_no_index_drift_between_models_and_migrations():
    """Every migrated index is declared on its model, and vice versa.

    A failure names the index: declare it in the model's `__table_args__`, or in
    `AUTOGENERATE_EXEMPT_INDEX_NAMES` if it is dialect-specific.
    """
    models.load_all_models()

    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        drift = [
            f"{diff[0]}: {diff[1].name} on {diff[1].table.name}"
            for diff in compare_metadata(context, BaseModel.metadata)
            if not isinstance(diff, list)
            and diff[0] in INDEX_DIFF_OPS
            and diff[1].name not in AUTOGENERATE_EXEMPT_INDEX_NAMES
        ]

    assert drift == []


def test_postgresql_fk_indexes_cover_every_unindexed_foreign_key():
    """`POSTGRESQL_FK_INDEXES` holds exactly the foreign keys that need it.

    MariaDB and MySQL index a foreign key implicitly unless its column already
    leads an index; PostgreSQL does not.
    """
    models.load_all_models()

    expected = {
        (table.name, f"ix_{table.name}_{column}", column)
        for table in BaseModel.metadata.tables.values()
        for constraint in table.foreign_key_constraints
        for column in [c.name for c in constraint.columns]
        if len(constraint.columns) == 1 and column not in _leading_columns(table)
    }

    assert expected == set(POSTGRESQL_FK_INDEXES)


@pytest.mark.parametrize(
    "fs_path,fs_name",
    [
        ("roms/nes", "Game (USA).zip"),
        ("roms/nes/Hacks & Tra'nslations", "Zelda [T-Eng].nes"),
        ("roms/nes/Ünïcøde", "Pokémon Édition Rouge.gb"),
        ("", ""),
        (None, None),
    ],
)
def test_the_migrated_full_path_digest_matches_the_models(
    fs_path: str | None, fs_name: str | None
):
    """0126 backfills `full_path_hash` in SQL; the app writes it from Python.

    A mismatch would make every pre-existing rom look new to the unique index.
    """
    with sync_engine.connect() as connection:
        digest = connection.execute(
            sa.text(
                f"SELECT {full_path_digest_sql(connection)} FROM "
                "(SELECT :fs_path AS fs_path, :fs_name AS fs_name) AS one_rom"
            ),
            {"fs_path": fs_path, "fs_name": fs_name},
        ).scalar_one()

    assert digest == compute_full_path_hash(fs_path, fs_name)


def _load_migration(filename: str) -> ModuleType:
    """Import a revision by file name, which no package path can reach."""
    path = Path(__file__).parent.parent / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    return migration


def _schema_of(
    connection: sa.Connection, table: str
) -> tuple[dict[str, bool], dict[str | None, tuple[tuple[str | None, ...], bool]]]:
    """Columns by nullability and indexes by (columns, uniqueness)."""
    inspector = sa.inspect(connection)
    return (
        {column["name"]: column["nullable"] for column in inspector.get_columns(table)},
        {
            index["name"]: (tuple(index["column_names"]), bool(index["unique"]))
            for index in inspector.get_indexes(table)
        },
    )


def _replay(connection: sa.Connection, filename: str) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        _load_migration(filename).upgrade()


# None of these is touched by a later revision, so replaying one over the
# migrated schema has to leave that schema exactly as it found it.
@pytest.mark.parametrize(
    "filename,table",
    [
        ("0111_physical_roms.py", "roms"),
        ("0120_container_adoptions.py", "streaming_container_adoptions"),
        ("0122_rom_similarity.py", "rom_similarity"),
        ("0123_recommendation_metadata.py", "roms"),
        ("0126_unique_rom_full_path.py", "roms"),
        ("0128_hltb_main_story_column.py", "roms"),
    ],
)
def test_a_revision_replayed_over_the_migrated_schema_is_a_no_op(
    filename: str, table: str
):
    with sync_engine.begin() as connection:
        before = _schema_of(connection, table)
        _replay(connection, filename)

        assert _schema_of(connection, table) == before


def test_the_rom_similarity_revision_fills_in_a_missing_index():
    """0122 meets its own table on a replay, with only some of its indexes.

    Alembic issues those as their own statements after the table, so a run can
    die between them.
    """
    migration = _load_migration("0122_rom_similarity.py")
    name, _ = migration.INDEXES[0]

    with sync_engine.begin() as connection:
        before = _schema_of(connection, migration.TABLE)
        with Operations.context(MigrationContext.configure(connection)) as operations:
            # The other one backs a foreign key, which MariaDB will not let go.
            operations.drop_index(name, table_name=migration.TABLE)
            migration.upgrade()

        assert _schema_of(connection, migration.TABLE) == before


def test_the_memory_card_revision_replays_under_the_one_that_prunes_it():
    """0119 re-creates the index 0125 drops, so the pair has to replay together.

    A real upgrade always runs 0125 after 0119; this pins that the second pass
    still lands on the same schema.
    """
    with sync_engine.begin() as connection:
        before = _schema_of(connection, "memory_card_versions")
        _replay(connection, "0119_memory_cards.py")
        _replay(connection, "0125_drop_redundant_indexes.py")

        assert _schema_of(connection, "memory_card_versions") == before


def test_the_full_path_hash_migration_resumes_an_interrupted_run(rom: Rom):
    """0126 finishes a run that died right after its ADD COLUMN.

    That run leaves the column with no digest, no NOT NULL and neither index.
    """
    migration = _load_migration("0126_unique_rom_full_path.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            migration.downgrade()
            operations.add_column(
                "roms",
                sa.Column(
                    migration.COLUMN_NAME, sa.String(length=FULL_PATH_HASH_LENGTH)
                ),
            )
            migration.upgrade()

        columns, indexes = _schema_of(connection, "roms")
        digest = connection.execute(
            sa.text(
                f"SELECT {migration.COLUMN_NAME} FROM roms WHERE id = :rom_id"
            ),  # nosec B608
            {"rom_id": rom.id},
        ).scalar_one()

    assert not columns[migration.COLUMN_NAME]
    assert indexes[migration.UNIQUE_INDEX_NAME][1]
    assert not indexes[migration.LOOKUP_INDEX_NAME][1]
    assert digest == compute_full_path_hash(rom.fs_path, rom.fs_name)


def test_the_hltb_migration_resumes_an_interrupted_run():
    """0128 keeps the generated column it already added and builds its index."""
    migration = _load_migration("0128_hltb_main_story_column.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            operations.drop_index(migration.INDEX_NAME, table_name="roms")
            migration.upgrade()

        _, indexes = _schema_of(connection, "roms")

    assert migration.INDEX_NAME in indexes


def test_has_column_reflects_the_migrated_schema():
    """The guard every replayed column add is skipped by."""
    with sync_engine.connect() as connection:
        assert has_column(connection, "roms", "generated_publishers")
        assert not has_column(connection, "roms", "no_such_column")


def test_the_publisher_split_column_add_replays():
    """0112's generated columns are added once, however often it runs.

    A run that dies on its trigger DDL (error 1419 on a binlog-enabled server
    without SUPER) leaves these committed, and the replay used to die on the
    duplicate column rather than resuming at the triggers.
    """
    migration = _load_migration("0112_publisher_developer_split.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration._add_generated_columns(is_postgresql(connection))

        assert has_column(connection, "roms", "generated_publishers")
        assert has_column(connection, "roms", "generated_developers")


@pytest.mark.parametrize(
    "drop_column",
    [False, True],
    ids=["died before the index", "died before the column"],
)
def test_the_state_disc_file_migration_resumes_an_interrupted_run(drop_column: bool):
    """0121 completes whatever a run that died partway left behind.

    Nothing else in the schema references these, so the interrupted states can
    be built for real: the foreign key and index missing, or all three.
    """
    migration = _load_migration("0121_state_disc_file.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            # The foreign key goes first: MariaDB refuses to drop a column it
            # still needs, and an index it still sits on.
            operations.drop_constraint(
                "fk_states_disc_file_id", "states", type_="foreignkey"
            )
            operations.drop_index("ix_states_disc_file_id", table_name="states")
            if drop_column:
                operations.drop_column("states", "disc_file_id")

            migration.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("states")}
        index = inspector.has_index("states", "ix_states_disc_file_id")
        foreign_keys = {key["name"] for key in inspector.get_foreign_keys("states")}

    assert "disc_file_id" in columns
    assert index
    assert "fk_states_disc_file_id" in foreign_keys


def _model_declared_generated_columns() -> list[sa.Column]:
    """The `roms` generated columns whose expression the model owns."""
    return [column for column in Rom.__table__.columns if column.computed is not None]


def test_every_model_declared_generated_column_is_pinned_to_a_revision():
    """Declaring a third `Computed` column without pinning it fails here."""
    declared = {column.name for column in _model_declared_generated_columns()}

    assert declared == set(GENERATED_COLUMN_REVISIONS)


@pytest.mark.parametrize(
    "dialect",
    [mysql.dialect(), postgresql.dialect()],
    ids=lambda dialect: dialect.name,
)
@pytest.mark.parametrize(
    ("column_name", "filename"), sorted(GENERATED_COLUMN_REVISIONS.items())
)
def test_the_model_expression_matches_the_revision_that_created_it(
    column_name: str, filename: str, dialect: sa.engine.Dialect
):
    """The model renders the SQL its revision emitted, on both dialects.

    Alembic reports a generated column being added or dropped but never a
    changed expression, so nothing else holds the two copies together.
    """
    migration = _load_migration(filename)
    column = Rom.__table__.c[column_name]
    literal = (
        migration._POSTGRES_EXPR
        if dialect.name == "postgresql"
        else migration._MARIA_EXPR
    )

    assert str(column.computed.sqltext.compile(dialect=dialect)) == literal


@pytest.mark.parametrize(
    "column", _model_declared_generated_columns(), ids=lambda column: column.name
)
def test_the_stored_generated_column_matches_the_model_expression(
    column: sa.Column, rom: Rom
):
    """The database computes what the model says it computes.

    The revision check above compares two strings; this one compares values, so
    a later revision that rebuilt the column is caught too.
    """
    db_rom_handler.update_rom(
        rom.id,
        {"regions": ["USA", "EUR"], "hltb_metadata": {"main_story": 7200}},
    )

    query = sa.select(
        Rom.__table__.c.id,
        column.computed.sqltext.label("model"),
        column.label("stored"),
    )
    with sync_engine.connect() as connection:
        rows = connection.execute(query).all()

    assert rows
    assert [
        (row.id, row.model, row.stored) for row in rows if row.model != row.stored
    ] == []
