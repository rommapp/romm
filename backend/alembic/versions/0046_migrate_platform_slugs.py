"""empty message

Revision ID: 0046_migrate_platform_slugs
Revises: 0045_roms_metadata_update
Create Date: 2025-07-24 15:24:04.331946

"""

import sqlalchemy as sa
from alembic import op

revision = "0046_migrate_platform_slugs"
down_revision = "0045_roms_metadata_update"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("temp_old_slug", sa.String(length=100), nullable=True)
        )
        batch_op.drop_column("logo_path")

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DATETIME(),
            type_=sa.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DATETIME(),
            type_=sa.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "fs_name", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_name_no_tags", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_name_no_ext", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_extension", existing_type=sa.VARCHAR(length=100), nullable=False
        )
        batch_op.alter_column(
            "fs_path", existing_type=sa.VARCHAR(length=1000), nullable=False
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role", existing_type=sa.Enum("VIEWER", "EDITOR", "ADMIN"), nullable=False
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=False
        )
        batch_op.alter_column(
            "ra_username",
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=255),
            existing_nullable=True,
        )

    # Update slugs already in the database
    connection = op.get_bind()
    for old_slug, new_slug in OLD_SLUGS_TO_NEW_MAP.items():
        connection.execute(
            sa.text(
                "UPDATE platforms SET slug = :new_slug, temp_old_slug = :old_slug WHERE slug = :old_slug"
            ),
            {"new_slug": new_slug, "old_slug": old_slug},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE platforms SET slug = temp_old_slug WHERE temp_old_slug IS NOT NULL"
        )
    )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "ra_username",
            existing_type=sa.String(length=255),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=True
        )
        batch_op.alter_column(
            "role", existing_type=sa.Enum("VIEWER", "EDITOR", "ADMIN"), nullable=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "fs_path", existing_type=sa.VARCHAR(length=1000), nullable=True
        )
        batch_op.alter_column(
            "fs_extension", existing_type=sa.VARCHAR(length=100), nullable=True
        )
        batch_op.alter_column(
            "fs_name_no_ext", existing_type=sa.VARCHAR(length=450), nullable=True
        )
        batch_op.alter_column(
            "fs_name_no_tags", existing_type=sa.VARCHAR(length=450), nullable=True
        )
        batch_op.alter_column(
            "fs_name", existing_type=sa.VARCHAR(length=450), nullable=True
        )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.TIMESTAMP(timezone=True),
            type_=sa.DATETIME(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.TIMESTAMP(timezone=True),
            type_=sa.DATETIME(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("logo_path", sa.VARCHAR(length=1000), nullable=True)
        )
        batch_op.drop_column("temp_old_slug")


OLD_SLUGS_TO_NEW_MAP = {}
