"""update to 1.8

Revision ID: 1.8
Revises: 1.7.1
Create Date: 2023-04-17 12:03:19.163501

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "1.8"
down_revision = "1.7.1"
branch_labels = None
depends_on = None


def _has_table(connection: sa.Connection, table_name: str) -> bool:
    return inspect(connection).has_table(table_name)


def _has_column(connection: sa.Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(connection, table_name):
        return False

    return column_name in {
        column["name"] for column in inspect(connection).get_columns(table_name)
    }


def _create_platforms_table() -> None:
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


def _copy_old_platforms() -> None:
    op.execute("""
        INSERT INTO platforms(igdb_id, sgdb_id, slug, fs_slug, name, logo_path, n_roms)
        SELECT
            old_platforms.igdb_id,
            old_platforms.sgdb_id,
            old_platforms.slug,
            old_platforms.slug,
            old_platforms.name,
            old_platforms.logo_path,
            old_platforms.n_roms
        FROM old_platforms
        LEFT JOIN platforms AS existing_platforms
            ON existing_platforms.fs_slug = old_platforms.slug
        WHERE existing_platforms.fs_slug IS NULL
        """)


def _upgrade_platforms(connection: sa.Connection) -> None:
    if (
        _has_table(connection, "platforms")
        and not _has_column(connection, "platforms", "fs_slug")
        and not _has_table(connection, "old_platforms")
    ):
        op.rename_table("platforms", "old_platforms")

    if _has_table(connection, "old_platforms"):
        if not _has_table(connection, "platforms"):
            _create_platforms_table()

        _copy_old_platforms()
        op.drop_table("old_platforms", if_exists=True)
    elif not _has_table(connection, "platforms"):
        _create_platforms_table()


def _upgrade_roms_columns(connection: sa.Connection) -> None:
    if not _has_table(connection, "roms") or _has_column(connection, "roms", "id"):
        return

    has_name = _has_column(connection, "roms", "name")
    has_r_name = _has_column(connection, "roms", "r_name")
    with op.batch_alter_table("roms") as batch_op:
        batch_op.add_column(
            sa.Column("p_name", sa.String(length=150), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("url_cover", sa.Text(), nullable=True), if_not_exists=True
        )
        if has_name and not has_r_name:
            batch_op.alter_column(
                "name",
                new_column_name="r_name",
                type_=sa.String(length=150),
                existing_type=sa.String(length=150),
            )
        batch_op.alter_column(
            "p_slug", existing_type=sa.String(length=50), nullable=False
        )
        batch_op.alter_column(
            "file_name", existing_type=sa.String(length=450), nullable=False
        )


def _create_roms_table() -> None:
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
        if_not_exists=True,
    )


def _copy_old_roms() -> None:
    op.execute("""
        INSERT INTO roms(
            r_igdb_id, p_igdb_id, r_sgdb_id, p_sgdb_id,
            p_slug, p_name, file_name, file_name_no_tags,
            file_extension, file_path, file_size,
            file_size_units, r_name, r_slug,
            summary, path_cover_s, path_cover_l,
            has_cover, region, revision, tags,
            multi, files, url_cover
        )
        SELECT
            old_roms.r_igdb_id,
            old_roms.p_igdb_id,
            old_roms.r_sgdb_id,
            old_roms.p_sgdb_id,
            old_roms.p_slug,
            old_roms.p_name,
            old_roms.file_name,
            old_roms.file_name_no_tags,
            old_roms.file_extension,
            old_roms.file_path,
            old_roms.file_size,
            old_roms.file_size_units,
            old_roms.r_name,
            old_roms.r_slug,
            old_roms.summary,
            old_roms.path_cover_s,
            old_roms.path_cover_l,
            old_roms.has_cover,
            old_roms.region,
            old_roms.revision,
            old_roms.tags,
            old_roms.multi,
            old_roms.files,
            old_roms.url_cover
        FROM old_roms
        LEFT JOIN roms AS existing_roms
            ON existing_roms.p_slug = old_roms.p_slug
            AND existing_roms.file_name = old_roms.file_name
        WHERE existing_roms.id IS NULL
        """)


def _upgrade_roms_table(connection: sa.Connection) -> None:
    if (
        _has_table(connection, "roms")
        and not _has_column(connection, "roms", "id")
        and not _has_table(connection, "old_roms")
    ):
        op.rename_table("roms", "old_roms")

    if _has_table(connection, "old_roms"):
        if not _has_table(connection, "roms"):
            _create_roms_table()

        _copy_old_roms()
        op.drop_table("old_roms", if_exists=True)
    elif not _has_table(connection, "roms"):
        _create_roms_table()


def upgrade() -> None:
    connection = op.get_bind()

    _upgrade_platforms(connection)
    _upgrade_roms_columns(connection)
    _upgrade_roms_table(connection)


def downgrade() -> None:
    with op.batch_alter_table("platforms") as batch_op:
        batch_op.drop_column("fs_slug", if_exists=True)
    with op.batch_alter_table("roms") as batch_op:
        batch_op.drop_column("id", if_exists=True)
        batch_op.drop_column("p_name", if_exists=True)
        batch_op.drop_column("url_cover", if_exists=True)
        batch_op.alter_column(
            "r_name",
            new_column_name="name",
            type_=sa.String(length=150),
            existing_type=sa.String(length=150),
        )
        batch_op.alter_column(
            "p_slug", existing_type=sa.String(length=50), nullable=False
        )
        batch_op.alter_column(
            "file_name", existing_type=sa.String(length=450), nullable=False
        )
