"""squashed initial schema up to 2.0.0

This migration squashes the legacy 1.6.2 -> 2.0.0 chain into a single
fresh-install create. It reproduces the exact schema those migrations
produced, so the rest of the chain (0009_models_refactor and later) applies
unchanged. Databases already stamped at 2.0.0 or later are unaffected.

Revision ID: 0001_initial_models
Revises:
Create Date: 2023-08-10 22:18:24.012779

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    json_array_build_func = (
        "jsonb_build_array()" if is_postgresql(connection) else "JSON_ARRAY()"
    )

    op.create_table(
        "platforms",
        sa.Column("igdb_id", sa.String(length=10), nullable=True),
        sa.Column("sgdb_id", sa.String(length=10), nullable=True),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("fs_slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=400), nullable=True),
        sa.Column("logo_path", sa.String(length=1000), nullable=True),
        sa.Column("n_roms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("fs_slug"),
        if_not_exists=True,
    )

    op.create_table(
        "roms",
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
        sa.Column("r_slug", sa.String(length=400), nullable=True),
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
        sa.Column(
            "url_screenshots",
            CustomJSON(),
            nullable=False,
            server_default=sa.text(f"({json_array_build_func})"),
        ),
        sa.Column(
            "path_screenshots",
            CustomJSON(),
            nullable=False,
            server_default=sa.text(f"({json_array_build_func})"),
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column(
            "role", sa.Enum("VIEWER", "EDITOR", "ADMIN", name="role"), nullable=True
        ),
        sa.Column("avatar_path", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_users_username"),
            ["username"],
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_username"), if_exists=True)

    op.drop_table("users", if_exists=True)
    op.drop_table("roms", if_exists=True)
    op.drop_table("platforms", if_exists=True)

    if is_postgresql(connection):
        ENUM(name="role").drop(connection, checkfirst=False)
