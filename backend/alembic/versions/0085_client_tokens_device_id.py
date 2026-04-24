"""Add device_id FK to client_tokens

Revision ID: 0081_client_tokens_device_id
Revises: 0080_devices_client_identifier
Create Date: 2026-04-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0085_client_tokens_device_id"
down_revision = "0084_devices_client_identifier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("client_tokens", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("device_id", sa.String(length=255), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_foreign_key(
            "fk_client_tokens_device_id",
            "devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_client_tokens_device_id",
            ["device_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("client_tokens", schema=None) as batch_op:
        # Drop FK before the backing index -- MariaDB refuses otherwise
        batch_op.drop_constraint("fk_client_tokens_device_id", type_="foreignkey")
        batch_op.drop_index("ix_client_tokens_device_id", if_exists=True)
        batch_op.drop_column("device_id", if_exists=True)
