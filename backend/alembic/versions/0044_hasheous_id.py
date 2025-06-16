"""empty message

Revision ID: 0044_hasheous_id
Revises: 0043_launchbox_id
Create Date: 2025-06-16 03:15:42.692551

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0044_hasheous_id"
down_revision = "0043_launchbox_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hasheous_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tgdb_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "hasheous_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )
        batch_op.create_index("idx_roms_hasheous_id", ["hasheous_id"], unique=False)
        batch_op.create_index("idx_roms_tgdb_id", ["tgdb_id"], unique=False)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hasheous_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tgdb_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("hasheous_id")
        batch_op.drop_column("tgdb_id")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_tgdb_id")
        batch_op.drop_index("idx_roms_hasheous_id")
        batch_op.drop_column("hasheous_metadata")
        batch_op.drop_column("tgdb_id")
        batch_op.drop_column("hasheous_id")
