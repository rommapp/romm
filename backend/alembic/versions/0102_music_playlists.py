"""Music playlists and per-user favorite tracks.

Revision ID: 0102_music_playlists
Revises: 0101_virtual_collection_roms
Create Date: 2026-07-22 00:00:00.000000

Tracks are referenced by (rom_id, md5_hash) rather than rom_file_id: rescans
purge and re-insert rom_files rows, so file ids churn while rom ids and file
content hashes are stable.

Every group's collections grants are mirrored onto the new playlists entity so
existing groups keep working without admin intervention. Per-user overrides are
intentionally not mirrored; admins can add playlist overrides where needed.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0102_music_playlists"
down_revision = "0101_virtual_collection_roms"
branch_labels = None
depends_on = None


def _grants_t() -> sa.TableClause:
    return sa.table(
        "permission_group_grants",
        sa.column("group_id", sa.Integer),
        sa.column("entity", sa.String),
        sa.column("action", sa.String),
        sa.column("own_only", sa.Boolean),
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = inspect(conn).get_table_names()

    if "music_playlists" not in existing_tables:
        op.create_table(
            "music_playlists",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=400), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("user_id", sa.Integer(), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "name", name="unique_music_playlist_user_name"
            ),
        )

    if "music_playlist_tracks" not in existing_tables:
        op.create_table(
            "music_playlist_tracks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("playlist_id", sa.Integer(), nullable=False),
            sa.Column("rom_id", sa.Integer(), nullable=False),
            sa.Column("md5_hash", sa.String(length=100), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(
                ["playlist_id"], ["music_playlists.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "playlist_id", "rom_id", "md5_hash", name="unique_music_playlist_track"
            ),
        )
        with op.batch_alter_table("music_playlist_tracks", schema=None) as batch_op:
            batch_op.create_index(
                "idx_music_playlist_tracks_playlist_position",
                ["playlist_id", "position"],
            )

    if "music_favorite_tracks" not in existing_tables:
        op.create_table(
            "music_favorite_tracks",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("rom_id", sa.Integer(), nullable=False),
            sa.Column("md5_hash", sa.String(length=100), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "rom_id", "md5_hash"),
        )

    _mirror_collections_grants(conn)


def _mirror_collections_grants(conn: sa.Connection) -> None:
    grants_t = _grants_t()

    existing_playlists = {
        (row.group_id, row.action)
        for row in conn.execute(
            sa.select(grants_t.c.group_id, grants_t.c.action).where(
                grants_t.c.entity == "playlists"
            )
        )
    }
    mirror_rows = [
        {
            "group_id": row.group_id,
            "entity": "playlists",
            "action": row.action,
            "own_only": row.own_only,
        }
        for row in conn.execute(
            sa.select(
                grants_t.c.group_id, grants_t.c.action, grants_t.c.own_only
            ).where(grants_t.c.entity == "collections")
        )
        if (row.group_id, row.action) not in existing_playlists
    ]
    if mirror_rows:
        conn.execute(grants_t.insert(), mirror_rows)


def downgrade() -> None:
    conn = op.get_bind()
    grants_t = _grants_t()
    conn.execute(sa.delete(grants_t).where(grants_t.c.entity == "playlists"))

    op.drop_table("music_playlist_tracks", if_exists=True)
    op.drop_table("music_favorite_tracks", if_exists=True)
    op.drop_table("music_playlists", if_exists=True)
