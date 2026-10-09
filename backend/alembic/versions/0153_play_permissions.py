"""Grant streaming and emulation read and write to every existing permission group

Revision ID: 0153_play_permissions
Revises: 0152_cross_user_smart_scopes
Create Date: 2026-10-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0153_play_permissions"
down_revision = "0152_cross_user_smart_scopes"
branch_labels = None
depends_on = None

ENTITIES = ("streaming", "emulation")
ACTIONS = ("read", "write")


def _groups_t() -> sa.TableClause:
    return sa.table("permission_groups", sa.column("id", sa.Integer))


def _grants_t() -> sa.TableClause:
    return sa.table(
        "permission_group_grants",
        sa.column("group_id", sa.Integer),
        sa.column("entity", sa.String),
        sa.column("action", sa.String),
        sa.column("own_only", sa.Boolean),
    )


def _overrides_t() -> sa.TableClause:
    return sa.table("user_permission_overrides", sa.column("entity", sa.String))


def upgrade() -> None:
    conn = op.get_bind()
    grants_t = _grants_t()

    existing = {
        (row.group_id, row.entity, row.action)
        for row in conn.execute(
            sa.select(grants_t.c.group_id, grants_t.c.entity, grants_t.c.action).where(
                grants_t.c.entity.in_(ENTITIES)
            )
        )
    }
    group_ids: list[int] = list(conn.execute(sa.select(_groups_t().c.id)).scalars())
    rows = [
        {"group_id": group_id, "entity": entity, "action": action, "own_only": False}
        for group_id in group_ids
        for entity in ENTITIES
        for action in ACTIONS
        if (group_id, entity, action) not in existing
    ]
    if rows:
        conn.execute(grants_t.insert(), rows)


def downgrade() -> None:
    # The previous PermEntity cannot load these rows, so none may remain.
    conn = op.get_bind()
    grants_t = _grants_t()
    overrides_t = _overrides_t()
    conn.execute(sa.delete(grants_t).where(grants_t.c.entity.in_(ENTITIES)))
    conn.execute(sa.delete(overrides_t).where(overrides_t.c.entity.in_(ENTITIES)))
