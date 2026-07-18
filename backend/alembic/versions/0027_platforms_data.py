"""platforms_data

Revision ID: 0027_platforms_data
Revises: 0026_romuser_status_fields
Create Date: 2024-11-17 23:05:31.038917

"""

import sqlalchemy as sa
from alembic import op

from models.platform import DEFAULT_COVER_ASPECT_RATIO

# revision identifiers, used by Alembic.
revision = "0027_platforms_data"
down_revision = "0026_romuser_status_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("category", sa.String(length=50), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("generation", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("family_name", sa.String(length=1000), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("family_slug", sa.String(length=1000), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("url", sa.String(length=1000), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("url_logo", sa.String(length=1000), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column(
                "aspect_ratio",
                sa.String(length=10),
                nullable=False,
                server_default=DEFAULT_COVER_ASPECT_RATIO,
            ),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("url_logo", if_exists=True)
        batch_op.drop_column("url", if_exists=True)
        batch_op.drop_column("family_name", if_exists=True)
        batch_op.drop_column("family_slug", if_exists=True)
        batch_op.drop_column("generation", if_exists=True)
        batch_op.drop_column("category", if_exists=True)
        batch_op.drop_column("aspect_ratio", if_exists=True)
