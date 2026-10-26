"""Rewrite own_only grants and overrides on entities that have no owner

Revision ID: 0154_ownerless_own_only
Revises: 0153_play_permissions
Create Date: 2026-10-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0154_ownerless_own_only"
down_revision = "0153_play_permissions"
branch_labels = None
depends_on = None

# models.permission.OWNABLE_PERM_ENTITIES when this revision was written.
OWNABLE_ENTITIES = (
    "collections",
    "playlists",
    "assets",
    "devices",
    "streaming",
    "emulation",
)


def _grants_t() -> sa.TableClause:
    return sa.table(
        "permission_group_grants",
        sa.column("entity", sa.String),
        sa.column("action", sa.String),
        sa.column("own_only", sa.Boolean),
    )


def _overrides_t() -> sa.TableClause:
    return sa.table(
        "user_permission_overrides",
        sa.column("entity", sa.String),
        sa.column("action", sa.String),
        sa.column("granted", sa.Boolean),
        sa.column("own_only", sa.Boolean),
    )


def upgrade() -> None:
    # Each row keeps the access it already gave: read and write fall back to
    # the coarse scope, delete has none and allowed nothing.
    conn = op.get_bind()
    grants_t = _grants_t()
    overrides_t = _overrides_t()

    ownerless_grant = sa.and_(
        grants_t.c.own_only == sa.true(),
        grants_t.c.entity.not_in(OWNABLE_ENTITIES),
    )
    conn.execute(
        sa.delete(grants_t).where(ownerless_grant, grants_t.c.action == "delete")
    )
    conn.execute(sa.update(grants_t).where(ownerless_grant).values(own_only=False))

    ownerless_override = sa.and_(
        overrides_t.c.own_only == sa.true(),
        overrides_t.c.entity.not_in(OWNABLE_ENTITIES),
    )
    conn.execute(
        sa.update(overrides_t)
        .where(ownerless_override, overrides_t.c.action == "delete")
        .values(granted=False, own_only=False)
    )
    conn.execute(
        sa.update(overrides_t).where(ownerless_override).values(own_only=False)
    )


def downgrade() -> None:
    # The rewritten rows grant the same access, so there is nothing to restore.
    pass
