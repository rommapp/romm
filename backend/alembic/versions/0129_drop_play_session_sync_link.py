"""Drop the play session's link to a sync session

``play_sessions.sync_session_id`` was written by one caller, the sync session's
own completion, and read by nothing: no query filters on it, the model's
relationship is ``lazy="raise"`` and never traversed, and no client asks for it.
It recorded "which sync moved the save this play produced", which the row cannot
actually answer, since a sync session records operation counts rather than the
saves themselves.

The desktop shell now reports playtime to ``/api/play-sessions`` in every case
rather than riding on the sync completion, so nothing writes the column at all.
``POST /api/sync/sessions/{id}/complete`` still ingests play sessions for a
client that sends them; they are simply stored like any other.

The constraint was created unnamed inside 0076's CREATE TABLE, so the server
chose its name. PostgreSQL drops a column's constraints with it; MariaDB and
MySQL refuse until the foreign key is gone, so it is looked up and dropped
first.

Revision ID: 0129_drop_play_session_sync_link
Revises: 0128_hltb_main_story_column
Create Date: 2026-09-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0129_drop_play_session_sync_link"
down_revision = "0128_hltb_main_story_column"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_play_sessions_sync_session_id"


def _mysql_fk_name(conn: sa.Connection) -> str | None:
    return conn.execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'play_sessions' "
            "AND COLUMN_NAME = 'sync_session_id' "
            "AND REFERENCED_TABLE_NAME = 'sync_sessions' LIMIT 1"
        )
    ).scalar()


def upgrade() -> None:
    conn = op.get_bind()

    if not is_postgresql(conn):
        name = _mysql_fk_name(conn)
        if name:
            op.drop_constraint(name, "play_sessions", type_="foreignkey")

    # Only PostgreSQL has this one: 0124 created the FK indexes MariaDB and
    # MySQL already imply, which is why no model declares it.
    op.drop_index(INDEX_NAME, table_name="play_sessions", if_exists=True)
    op.drop_column("play_sessions", "sync_session_id", if_exists=True)


def downgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "play_sessions",
        sa.Column("sync_session_id", sa.Integer(), nullable=True),
        if_not_exists=True,
    )
    # Order matters on MariaDB: the index backs the constraint, so it comes
    # first. The name is the shell's own rather than the server's, since an
    # unnamed constraint is what made the drop above dialect-specific.
    op.create_index(
        INDEX_NAME, "play_sessions", ["sync_session_id"], if_not_exists=True
    )
    op.create_foreign_key(
        "fk_play_sessions_sync_session_id",
        "play_sessions",
        "sync_sessions",
        ["sync_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    if is_postgresql(conn):
        return
    # MariaDB and MySQL index a single-column FK implicitly, so the explicit one
    # above is redundant there and 0124 only ever created it on PostgreSQL.
    op.drop_index(INDEX_NAME, table_name="play_sessions", if_exists=True)
