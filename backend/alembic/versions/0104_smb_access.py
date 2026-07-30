"""Add managed SMB users and platform permissions

Revision ID: 0104_smb_access
Revises: 0103_roms_facets_provider_ids
Create Date: 2026-07-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0104_smb_access"
down_revision = "0103_roms_facets_provider_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smb_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_smb_users_username", "smb_users", ["username"], unique=True)

    op.create_table(
        "smb_platform_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("smb_user_id", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column(
            "access",
            sa.Enum(
                "read",
                "write",
                name="smbaccessmode",
                native_enum=False,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platforms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["smb_user_id"], ["smb_users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "smb_user_id", "platform_id", name="uq_smb_user_platform"
        ),
    )
    op.create_index(
        "ix_smb_platform_permissions_platform_id",
        "smb_platform_permissions",
        ["platform_id"],
    )
    op.create_index(
        "ix_smb_platform_permissions_smb_user_id",
        "smb_platform_permissions",
        ["smb_user_id"],
    )


def downgrade() -> None:
    op.drop_table("smb_platform_permissions")
    op.drop_table("smb_users")
