"""Granular permission system: groups, grants, per-user overrides, hidden entities.

Single migration for the whole permissions feature (tables, group colour, and
the legacy-group backfill). Backfills so that NO user gains or loses access on
upgrade:

  * "Viewer (legacy)" group reproduces the old non-kiosk default user
    (WRITE_SCOPES): read the library, manage only own collections/assets/devices.
  * "Editor (legacy)" group reproduces EDIT_SCOPES: viewer + library-wide write
    AND delete of roms/platforms/firmware (today's deletes gate on *_WRITE, so
    editors can already delete -- preserved here as explicit delete grants).
  * Existing users are assigned to the matching group by their current role.
    Admins are left unassigned (they bypass groups entirely).

The seeded grant matrix is the frozen twin of ``handler/auth/permissions_map.py``;
``tests/handler/auth/test_permissions_parity.py`` keeps the two in lockstep.

Revision ID: 0091_permission_system
Revises: 0091_unique_platform_fs_name
Create Date: 2026-06-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0091_permission_system"
down_revision = "0091_unique_platform_fs_name"
branch_labels = None
depends_on = None


# (entity, action, own_only) -- frozen snapshot, mirrors permissions_map.py.
VIEWER_GRANTS = [
    ("roms", "read", False),
    ("platforms", "read", False),
    ("firmware", "read", False),
    ("collections", "read", False),
    ("collections", "write", True),
    ("collections", "delete", True),
    ("assets", "read", False),
    ("assets", "write", True),
    ("assets", "delete", True),
    ("devices", "read", True),
    ("devices", "write", True),
    ("devices", "delete", True),
]
EDITOR_EXTRA = [
    ("roms", "write", False),
    ("roms", "delete", False),
    ("platforms", "write", False),
    ("platforms", "delete", False),
    ("firmware", "write", False),
    ("firmware", "delete", False),
]
EDITOR_GRANTS = VIEWER_GRANTS + EDITOR_EXTRA

# Legacy-group colours echoing the old role tones (viewer -> blue,
# editor -> amber) so they look intentional out of the box.
VIEWER_COLOR = "#3b82f6"
EDITOR_COLOR = "#f59e0b"


def _timestamp_cols() -> tuple[sa.Column, sa.Column]:
    # Fresh Column objects per call: a Column instance can only belong to one
    # table, so the four create_table calls each need their own pair.
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade() -> None:
    op.create_table(
        "permission_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "description",
            sa.String(length=1000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("color", sa.String(length=9), nullable=True),
        *_timestamp_cols(),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("permission_groups") as batch_op:
        batch_op.create_index(
            "ix_permission_groups_name", ["name"], unique=True, if_not_exists=True
        )
        batch_op.create_index(
            "ix_permission_groups_is_default", ["is_default"], if_not_exists=True
        )

    op.create_table(
        "permission_group_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column(
            "own_only", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        *_timestamp_cols(),
        sa.ForeignKeyConstraint(
            ["group_id"], ["permission_groups.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "entity", "action", name="uq_group_grant"),
        if_not_exists=True,
    )
    with op.batch_alter_table("permission_group_grants") as batch_op:
        batch_op.create_index(
            "ix_permission_group_grants_group_id", ["group_id"], if_not_exists=True
        )

    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "own_only", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        *_timestamp_cols(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "entity", "action", name="uq_user_override"),
        if_not_exists=True,
    )
    with op.batch_alter_table("user_permission_overrides") as batch_op:
        batch_op.create_index(
            "ix_user_permission_overrides_user_id", ["user_id"], if_not_exists=True
        )

    op.create_table(
        "hidden_entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        *_timestamp_cols(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["permission_groups.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity", "entity_id", "user_id", "group_id", name="uq_hidden_entity"
        ),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (group_id IS NULL)",
            name="ck_hidden_one_principal",
        ),
        if_not_exists=True,
    )
    with op.batch_alter_table("hidden_entities") as batch_op:
        batch_op.create_index(
            "ix_hidden_entities_entity_id", ["entity_id"], if_not_exists=True
        )
        batch_op.create_index(
            "ix_hidden_entities_user_id", ["user_id"], if_not_exists=True
        )
        batch_op.create_index(
            "ix_hidden_entities_group_id", ["group_id"], if_not_exists=True
        )
        batch_op.create_index(
            "idx_hidden_user_lookup", ["user_id", "entity"], if_not_exists=True
        )
        batch_op.create_index(
            "idx_hidden_group_lookup", ["group_id", "entity"], if_not_exists=True
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("permission_group_id", sa.Integer(), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_foreign_key(
            "fk_users_permission_group_id",
            "permission_groups",
            ["permission_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_users_permission_group_id",
            ["permission_group_id"],
            if_not_exists=True,
        )

    _seed_legacy_groups()


def _seed_legacy_groups() -> None:
    conn = op.get_bind()

    groups_t = sa.table(
        "permission_groups",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("is_system", sa.Boolean),
        sa.column("color", sa.String),
    )
    grants_t = sa.table(
        "permission_group_grants",
        sa.column("group_id", sa.Integer),
        sa.column("entity", sa.String),
        sa.column("action", sa.String),
        sa.column("own_only", sa.Boolean),
    )

    conn.execute(
        groups_t.insert(),
        [
            {
                "name": "Viewer (legacy)",
                "description": (
                    "Read the library; manage only your own collections, "
                    "assets and devices. Reproduces the pre-upgrade default user."
                ),
                "is_default": True,
                "is_system": True,
                "color": VIEWER_COLOR,
            },
            {
                "name": "Editor (legacy)",
                "description": (
                    "Viewer access plus library-wide create/edit/delete of "
                    "roms, platforms and firmware. Reproduces the pre-upgrade "
                    "editor role."
                ),
                "is_default": False,
                "is_system": True,
                "color": EDITOR_COLOR,
            },
        ],
    )

    name_to_id = {
        name: gid
        for gid, name in conn.execute(
            sa.select(groups_t.c.id, groups_t.c.name).where(
                groups_t.c.name.in_(["Viewer (legacy)", "Editor (legacy)"])
            )
        ).all()
    }
    viewer_id = name_to_id["Viewer (legacy)"]
    editor_id = name_to_id["Editor (legacy)"]

    grant_rows = [
        {"group_id": viewer_id, "entity": e, "action": a, "own_only": o}
        for (e, a, o) in VIEWER_GRANTS
    ] + [
        {"group_id": editor_id, "entity": e, "action": a, "own_only": o}
        for (e, a, o) in EDITOR_GRANTS
    ]
    conn.execute(grants_t.insert(), grant_rows)

    # Assign existing users to the group matching their current role. Admins are
    # intentionally left NULL: they bypass the group system.
    conn.execute(
        sa.text("UPDATE users SET permission_group_id = :gid WHERE role = 'EDITOR'"),
        {"gid": editor_id},
    )
    conn.execute(
        sa.text("UPDATE users SET permission_group_id = :gid WHERE role = 'VIEWER'"),
        {"gid": viewer_id},
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_permission_group_id", type_="foreignkey")
        batch_op.drop_index("ix_users_permission_group_id", if_exists=True)
        batch_op.drop_column("permission_group_id", if_exists=True)

    op.drop_table("hidden_entities", if_exists=True)
    op.drop_table("user_permission_overrides", if_exists=True)
    op.drop_table("permission_group_grants", if_exists=True)
    op.drop_table("permission_groups", if_exists=True)
