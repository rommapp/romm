"""rename platforms scanned with their ScreenScraper sibling's name

Revision ID: 0143_sibling_platform_names
Revises: 0142_state_core
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0143_sibling_platform_names"
down_revision = "0142_state_core"
branch_labels = None
depends_on = None

# (slug, name a scan stored, correct name)
RENAMES = (
    ("c128", "Commodore 64", "Commodore 128"),
    ("videopac-g7400", "Videopac G7000", "Videopac+ G7400"),
)


def upgrade() -> None:
    # Only the stale name is replaced, so a name set by another provider stays.
    for slug, stale, name in RENAMES:
        op.execute(
            sa.text(
                "UPDATE platforms SET name = :name WHERE slug = :slug AND name = :stale"
            ).bindparams(name=name, slug=slug, stale=stale)
        )


def downgrade() -> None:
    pass
