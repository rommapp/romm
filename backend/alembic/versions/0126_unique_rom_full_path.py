"""Key the unique roms index on the full path instead of the file name

A custom library structure lets a platform hold identically-named files in
different folders. The path is indexed through a digest because fs_path plus
fs_name is 5804 bytes of utf8mb4, over InnoDB's 3072-byte key limit; the
(platform_id, fs_name) index stays for the scan loop, demoted to non-unique.

`roms` is the widest table in the schema (80-odd columns, a JSON metadata blob
per provider, 30-odd indexes), so every pass over it is the expensive thing
here and this revision is shaped to make as few as possible:

- The column is born NOT NULL behind an empty-string default. Turning a column
  NOT NULL afterwards is the one change InnoDB cannot make without rebuilding
  the table and every index on it, while adding one with a default is
  metadata-only (INSTANT on MariaDB 10.3+ and MySQL 8.0.12+, no rewrite on
  PostgreSQL 11+). Retiring the default afterwards is metadata-only too.
- The backfill walks the primary key in chunks and commits each one, so a
  container stopped mid-upgrade keeps the digests it already wrote. A single
  UPDATE over the whole table holds an undo log the size of the library and
  rolls all of it back, which on a large library never finishes across
  restarts.
- The two indexes are built in one ALTER TABLE on MySQL and MariaDB, which
  scan the table once per statement. They are not dropped and re-added in that
  same statement: reusing an index name in one ALTER forces the copy algorithm.

Revision ID: 0126_unique_rom_full_path
Revises: 0125_drop_redundant_indexes
Create Date: 2026-09-07 00:00:00.000000

"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import sqlalchemy as sa
from alembic import op

from logger.logger import log
from models.rom import FULL_PATH_HASH_LENGTH
from utils.database import full_path_digest_sql, is_postgresql

# revision identifiers, used by Alembic.
revision = "0126_unique_rom_full_path"
down_revision = "0125_drop_redundant_indexes"
branch_labels = None
depends_on = None

COLUMN_NAME = "full_path_hash"
LOOKUP_INDEX_NAME = "idx_roms_platform_id_fs_name"
UNIQUE_INDEX_NAME = "idx_roms_platform_id_full_path_hash"

# Rows per backfill statement. Low enough to keep each transaction's undo log
# and lock set small on modest hardware, high enough that the per-statement
# round trip disappears into the work.
BACKFILL_CHUNK_SIZE = 5_000

# Matches a row the backfill has not reached, under either shape the column can
# have: the default this revision gives it, or the NULL a 5.3.0 alpha left.
_PENDING = f"({COLUMN_NAME} IS NULL OR {COLUMN_NAME} = '')"


@contextmanager
def _committing_each_chunk() -> Iterator[None]:
    """Commit as the backfill goes, where the migration owns its transaction.

    `autocommit_block` takes over that transaction, which a caller that opened
    one of its own (the migration tests) never handed to alembic.
    """
    context = op.get_context()
    if context._in_external_transaction:
        yield
    else:
        with context.autocommit_block():
            yield


def _backfill() -> None:
    """Fill the digest in primary-key order, one committed chunk at a time."""
    connection = op.get_bind()
    total = connection.execute(sa.text("SELECT COUNT(*) FROM roms")).scalar_one()
    if not total:
        return

    log.info(f"[0126] computing the path digest for {total} roms")

    select_chunk = sa.text(
        f"SELECT id FROM roms WHERE {_PENDING} AND id > :cursor "  # nosec B608
        f"ORDER BY id LIMIT {BACKFILL_CHUNK_SIZE}"
    )
    update_chunk = sa.text(
        f"UPDATE roms SET {COLUMN_NAME} = {full_path_digest_sql(connection)} "  # nosec B608
        f"WHERE {_PENDING} AND id > :cursor AND id <= :last"
    )

    with _committing_each_chunk():
        # An autocommit block swaps the connection out from under the context.
        chunked = op.get_bind()
        cursor = done = 0
        while True:
            ids = chunked.execute(select_chunk, {"cursor": cursor}).scalars().all()
            if not ids:
                break

            chunked.execute(update_chunk, {"cursor": cursor, "last": ids[-1]})
            cursor, done = ids[-1], done + len(ids)
            log.info(f"[0126] {done}/{total} roms")


def _create_indexes(wanted: Sequence[tuple[str, list[str], bool]]) -> None:
    """Build the indexes in a single pass over the table where the dialect can."""
    if not wanted:
        return

    if is_postgresql(op.get_bind()):
        for name, columns, unique in wanted:
            op.create_index(name, "roms", columns, unique=unique, if_not_exists=True)
        return

    clauses = ", ".join(
        f"ADD {'UNIQUE ' if unique else ''}INDEX {name} ({', '.join(columns)})"
        for name, columns, unique in wanted
    )
    op.execute(f"ALTER TABLE roms {clauses}")  # nosec B608


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns("roms")}
    indexes = {index["name"]: index for index in inspector.get_indexes("roms")}
    column = columns.get(COLUMN_NAME)

    # A crash mid-migration keeps what it created while the alembic version
    # stays behind, so each step is guarded and a replay resumes where it stopped.
    if column is None:
        op.execute(
            f"ALTER TABLE roms ADD COLUMN {COLUMN_NAME} "  # nosec B608
            f"VARCHAR({FULL_PATH_HASH_LENGTH}) NOT NULL DEFAULT ''"
        )
        needs_not_null, needs_backfill = False, True
    else:
        # The default outlives the backfill, so it is what says the rows still
        # need filling. A nullable column is one a 5.3.0 alpha added.
        needs_not_null = column["nullable"]
        needs_backfill = needs_not_null or column["default"] is not None

    if needs_backfill:
        _backfill()

        if needs_not_null:
            # Only the alpha installs above reach this, and only they pay for
            # the table rebuild it costs.
            with op.batch_alter_table("roms", schema=None) as batch_op:
                batch_op.alter_column(
                    COLUMN_NAME,
                    existing_type=sa.String(length=FULL_PATH_HASH_LENGTH),
                    nullable=False,
                )

        # A no-op against an alpha's column, which carries no default to drop.
        op.execute(f"ALTER TABLE roms ALTER COLUMN {COLUMN_NAME} DROP DEFAULT")

    # 0091 made this index unique; the digest carries that role now.
    lookup_stale = (
        LOOKUP_INDEX_NAME not in indexes or indexes[LOOKUP_INDEX_NAME]["unique"]
    )
    if lookup_stale:
        op.drop_index(LOOKUP_INDEX_NAME, table_name="roms", if_exists=True)

    wanted: list[tuple[str, list[str], bool]] = []
    if UNIQUE_INDEX_NAME not in indexes:
        wanted.append((UNIQUE_INDEX_NAME, ["platform_id", COLUMN_NAME], True))
    if lookup_stale:
        wanted.append((LOOKUP_INDEX_NAME, ["platform_id", "fs_name"], False))

    _create_indexes(wanted)


def downgrade() -> None:
    connection = op.get_bind()

    # Refuse rather than delete the roms a narrower index cannot hold, along
    # with their saves, notes and collection membership.
    duplicates = connection.execute(sa.text("""
            SELECT COUNT(*) FROM (
                SELECT platform_id, fs_name
                FROM roms
                GROUP BY platform_id, fs_name
                HAVING COUNT(*) > 1
            ) AS dupes
            """)).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"Cannot downgrade: {duplicates} file name(s) are shared by more "
            "than one rom on the same platform, which this revision's unique "
            "index forbids. Group the roms table by platform_id and fs_name to "
            "find them, then move or delete the extra copies and retry."
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(LOOKUP_INDEX_NAME, if_exists=True)
        batch_op.create_index(
            LOOKUP_INDEX_NAME,
            ["platform_id", "fs_name"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.drop_index(UNIQUE_INDEX_NAME, if_exists=True)

    op.drop_column("roms", COLUMN_NAME)
