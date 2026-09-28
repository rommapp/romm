"""Drop the play session's link to a sync session

Revision ID: 0135_drop_play_session_sync_link
Revises: 0134_gallery_sort_indexes
Create Date: 2026-09-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0135_drop_play_session_sync_link"
down_revision = "0134_gallery_sort_indexes"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_play_sessions_sync_session_id"
FK_NAME = "fk_play_sessions_sync_session_id"


def _existing_fk_name(conn: sa.Connection) -> str | None:
    """The constraint on this column, under whatever name its server chose."""
    for fk in sa.inspect(conn).get_foreign_keys("play_sessions"):
        if fk.get("referred_table") == "sync_sessions" and fk.get(
            "constrained_columns"
        ) == ["sync_session_id"]:
            return fk.get("name") or FK_NAME
    return None


def upgrade() -> None:
    conn = op.get_bind()

    # PostgreSQL drops a column's constraints with it; MariaDB and MySQL refuse
    # until the foreign key is gone, and 0076 left it for the server to name.
    if not is_postgresql(conn):
        name = _existing_fk_name(conn)
        if name:
            op.drop_constraint(name, "play_sessions", type_="foreignkey")

    op.drop_index(INDEX_NAME, table_name="play_sessions", if_exists=True)
    op.drop_column("play_sessions", "sync_session_id", if_exists=True)


def downgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "play_sessions",
        sa.Column("sync_session_id", sa.Integer(), nullable=True),
        if_not_exists=True,
    )
    # Only on PostgreSQL, which is where 0124 put it: MariaDB and MySQL index a
    # single-column foreign key themselves, and the index they make backs the
    # constraint, so one created here could not be dropped again.
    if is_postgresql(conn):
        op.create_index(
            INDEX_NAME, "play_sessions", ["sync_session_id"], if_not_exists=True
        )
    # Guarded like the steps above, since these databases commit each one and a
    # downgrade that stopped halfway is replayed from the top.
    if not _existing_fk_name(conn):
        op.create_foreign_key(
            FK_NAME,
            "play_sessions",
            "sync_sessions",
            ["sync_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
