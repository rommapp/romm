"""Drop columns that duplicate derivable data

Revision ID: 0145_drop_derivable_columns
Revises: 0144_user_oidc_sub
Create Date: 2026-09-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.interfaces import ReflectedColumn

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0145_drop_derivable_columns"
down_revision = "0144_user_oidc_sub"
branch_labels = None
depends_on = None

DOC_META_TABLE = "rom_file_doc_meta"
DOC_META_INDEX_NAME = "idx_rom_file_doc_meta_rom_id"
DOC_META_FK_NAME = "fk_rom_file_doc_meta_rom_id"


def _doc_meta_fk_name(conn: sa.Connection) -> str | None:
    """The constraint on `rom_file_doc_meta.rom_id`, under whatever name its server chose."""
    for fk in sa.inspect(conn).get_foreign_keys(DOC_META_TABLE):
        if fk.get("referred_table") == "roms" and fk.get("constrained_columns") == [
            "rom_id"
        ]:
            return fk.get("name") or DOC_META_FK_NAME
    return None


def _column(conn: sa.Connection, table: str, name: str) -> ReflectedColumn:
    """The reflected `table.name`, which the step before has just added."""
    return next(c for c in sa.inspect(conn).get_columns(table) if c["name"] == name)


def upgrade() -> None:
    conn = op.get_bind()

    op.drop_column("smart_collections", "rom_count", if_exists=True)

    # PostgreSQL drops a column's constraints with it; MariaDB and MySQL refuse
    # while the foreign key stands, and 0110 left it for the server to name.
    if not is_postgresql(conn):
        name = _doc_meta_fk_name(conn)
        if name:
            op.drop_constraint(name, DOC_META_TABLE, type_="foreignkey")

    op.drop_index(DOC_META_INDEX_NAME, table_name=DOC_META_TABLE, if_exists=True)
    op.drop_column(DOC_META_TABLE, "rom_id", if_exists=True)


def downgrade() -> None:
    conn = op.get_bind()

    # A temporary server default lets existing rows take the NOT NULL column.
    op.add_column(
        "smart_collections",
        sa.Column("rom_count", sa.Integer(), nullable=False, server_default="0"),
        if_not_exists=True,
    )
    op.execute(
        "UPDATE smart_collections SET rom_count = jsonb_array_length(rom_ids)"
        if is_postgresql(conn)
        else "UPDATE smart_collections SET rom_count = JSON_LENGTH(rom_ids)"
    )
    if _column(conn, "smart_collections", "rom_count")["default"] is not None:
        op.alter_column(
            "smart_collections",
            "rom_count",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default=None,
        )

    op.add_column(
        DOC_META_TABLE,
        sa.Column("rom_id", sa.Integer(), nullable=True),
        if_not_exists=True,
    )
    op.execute(
        "UPDATE rom_file_doc_meta SET rom_id = ("
        "SELECT rom_files.rom_id FROM rom_files"
        " WHERE rom_files.id = rom_file_doc_meta.rom_file_id)"
    )
    if _column(conn, DOC_META_TABLE, "rom_id")["nullable"]:
        op.alter_column(
            DOC_META_TABLE, "rom_id", existing_type=sa.Integer(), nullable=False
        )
    # Before the foreign key, so MariaDB and MySQL back it with this index
    # rather than one of their own that the upgrade would leave behind.
    op.create_index(DOC_META_INDEX_NAME, DOC_META_TABLE, ["rom_id"], if_not_exists=True)
    if not _doc_meta_fk_name(conn):
        op.create_foreign_key(
            DOC_META_FK_NAME,
            DOC_META_TABLE,
            "roms",
            ["rom_id"],
            ["id"],
            ondelete="CASCADE",
        )
