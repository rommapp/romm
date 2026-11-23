"""move platforms off the retired MAME-only arcade board slugs

Revision ID: 0155_retired_arcade_slugs
Revises: 0154_ownerless_own_only
Create Date: 2026-10-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0155_retired_arcade_slugs"
down_revision = "0154_ownerless_own_only"
branch_labels = None
depends_on = None

RETIRED_SLUGS = (
    "cps1",
    "cps2",
    "cps3",
    "model1",
    "system-32",
    "system16",
    "system32",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE platforms SET slug = 'arcade' WHERE LOWER(slug) IN :slugs"
        ).bindparams(sa.bindparam("slugs", value=RETIRED_SLUGS, expanding=True))
    )


def downgrade() -> None:
    # The old slug is gone, so only a folder named after it can restore it.
    op.execute(
        sa.text(
            "UPDATE platforms SET slug = LOWER(fs_slug) "
            "WHERE slug = 'arcade' AND LOWER(fs_slug) IN :slugs"
        ).bindparams(sa.bindparam("slugs", value=RETIRED_SLUGS, expanding=True))
    )
