"""Add walkthrough document support.

Adds the WALKTHROUGH value to the rom_files.category enum, plus two tables:
- rom_file_doc_meta: provenance sidecar for document-category files
- rom_file_user: per-user reading progress for document-category files

Revision ID: 0098_walkthrough_docs
Revises: 0097_roms_platform_fs_size_index
Create Date: 2026-07-18 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0098_walkthrough_docs"
down_revision = "0097_roms_platform_fs_size_index"
branch_labels = None
depends_on = None

# Full enum member set including WALKTHROUGH, in model declaration order.
ROM_FILE_CATEGORY_VALUES = (
    "GAME",
    "DLC",
    "HACK",
    "MANUAL",
    "WALKTHROUGH",
    "PATCH",
    "UPDATE",
    "MOD",
    "DEMO",
    "TRANSLATION",
    "PROTOTYPE",
    "CHEAT",
    "SOUNDTRACK",
    "SCREENSHOT",
)

# The pre-walkthrough set, used to narrow the enum back on downgrade.
ROM_FILE_CATEGORY_VALUES_PRE = tuple(
    v for v in ROM_FILE_CATEGORY_VALUES if v != "WALKTHROUGH"
)


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Extend the rom_files.category enum with WALKTHROUGH.
    if is_postgresql(connection):
        # `ALTER TYPE ... ADD VALUE` must run outside a transaction in PostgreSQL.
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE romfilecategory ADD VALUE IF NOT EXISTS 'WALKTHROUGH'"
            )
    else:
        with op.batch_alter_table("rom_files", schema=None) as batch_op:
            batch_op.alter_column(
                "category",
                type_=sa.Enum(*ROM_FILE_CATEGORY_VALUES, name="romfilecategory"),
                nullable=True,
            )

    # 2. Provenance sidecar for document-category files.
    op.create_table(
        "rom_file_doc_meta",
        sa.Column("rom_file_id", sa.Integer(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("UPLOAD", "GAMEFAQS", "SCRAPER", name="docsource"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=512), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["rom_file_id"], ["rom_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rom_file_id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("rom_file_doc_meta", schema=None) as batch_op:
        batch_op.create_index(
            "idx_rom_file_doc_meta_rom_id",
            ["rom_id"],
            unique=False,
            if_not_exists=True,
        )

    # 3. Per-user reading progress for document-category files.
    op.create_table(
        "rom_file_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rom_file_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_page", sa.Integer(), nullable=True),
        sa.Column("finished", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["rom_file_id"], ["rom_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rom_file_id", "user_id", name="unique_rom_file_user"),
        if_not_exists=True,
    )
    with op.batch_alter_table("rom_file_user", schema=None) as batch_op:
        batch_op.create_index(
            "idx_rom_file_user",
            ["rom_file_id", "user_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()

    op.drop_table("rom_file_user", if_exists=True)
    op.drop_table("rom_file_doc_meta", if_exists=True)

    # PostgreSQL cannot drop an enum value, so leave WALKTHROUGH in place there.
    # The docsource type is dropped with its table on PG; drop it explicitly in
    # case create_table left it behind.
    if is_postgresql(connection):
        op.execute("DROP TYPE IF EXISTS docsource")
        return

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "category",
            type_=sa.Enum(*ROM_FILE_CATEGORY_VALUES_PRE, name="romfilecategory"),
            nullable=True,
        )
