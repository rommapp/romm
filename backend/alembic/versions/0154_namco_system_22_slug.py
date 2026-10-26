"""Rename the system-32 platform slug to namco-system-22

Revision ID: 0154_namco_system_22_slug
Revises: 0153_play_permissions
Create Date: 2026-10-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0154_namco_system_22_slug"
down_revision = "0153_play_permissions"
branch_labels = None
depends_on = None

OLD_SLUG = "system-32"
NEW_SLUG = "namco-system-22"


def _rename(old: str, new: str) -> None:
    op.execute(
        sa.text("UPDATE platforms SET slug = :new WHERE slug = :old").bindparams(
            old=old, new=new
        )
    )


def upgrade() -> None:
    _rename(OLD_SLUG, NEW_SLUG)


def downgrade() -> None:
    _rename(NEW_SLUG, OLD_SLUG)
