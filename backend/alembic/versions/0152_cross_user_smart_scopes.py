"""clear smart collections scoped to another user's private collection

Revision ID: 0152_cross_user_smart_scopes
Revises: 0151_state_content_hash
Create Date: 2026-10-09 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0152_cross_user_smart_scopes"
down_revision = "0151_state_content_hash"
branch_labels = None
depends_on = None

collections = sa.table(
    "collections",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("is_public", sa.Boolean),
)
smart_collections = sa.table(
    "smart_collections",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("filter_criteria", CustomJSON()),
    sa.column("rom_ids", CustomJSON()),
    sa.column("path_covers_small", CustomJSON()),
    sa.column("path_covers_large", CustomJSON()),
)


def upgrade() -> None:
    # Their cached membership predates the ownership check and would match
    # nothing now, so it is emptied rather than left readable until a refresh.
    conn = op.get_bind()
    visible = {
        row.id: (row.user_id, bool(row.is_public))
        for row in conn.execute(sa.select(collections))
    }
    rows = conn.execute(
        sa.select(
            smart_collections.c.id,
            smart_collections.c.user_id,
            smart_collections.c.filter_criteria,
        )
    ).all()

    stale_ids = []
    for smart_id, owner_id, criteria in rows:
        if not isinstance(criteria, dict):
            continue
        try:
            collection_id = int(criteria.get("collection_id") or 0)
        except (TypeError, ValueError):
            continue
        if not collection_id:
            continue

        user_id, is_public = visible.get(collection_id, (None, False))
        if not is_public and user_id != owner_id:
            stale_ids.append(smart_id)

    if stale_ids:
        conn.execute(
            sa.update(smart_collections)
            .where(smart_collections.c.id.in_(stale_ids))
            .values(rom_ids=[], path_covers_small=[], path_covers_large=[])
        )


def downgrade() -> None:
    pass
