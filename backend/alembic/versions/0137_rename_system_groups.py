"""Key the seeded permission groups and rename them to Viewer and Editor

`system_key` replaces `is_system`. Admin renames, name clashes and edited
descriptions are left alone.

Revision ID: 0137_rename_system_groups
Revises: 0136_deleted_assets
Create Date: 2026-09-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import has_column

# revision identifiers, used by Alembic.
revision = "0137_rename_system_groups"
down_revision = "0136_deleted_assets"
branch_labels = None
depends_on = None

# (system key, old name, new name, old description, new description)
RENAMES = (
    (
        "viewer",
        "Viewer (legacy)",
        "Viewer",
        "Read the library; manage only your own collections, "
        "assets and devices. Reproduces the pre-upgrade default user.",
        "Read the library; manage only your own collections, assets and devices.",
    ),
    (
        "editor",
        "Editor (legacy)",
        "Editor",
        "Viewer access plus library-wide create/edit/delete of "
        "roms, platforms and firmware. Reproduces the pre-upgrade "
        "editor role.",
        "Viewer access plus library-wide create/edit/delete of "
        "roms, platforms and firmware.",
    ),
)

groups_t = sa.table(
    "permission_groups",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("is_system", sa.Boolean),
    sa.column("system_key", sa.String),
)


def _rename(
    key: str, from_name: str, to_name: str, from_desc: str, to_desc: str
) -> None:
    conn = op.get_bind()
    # `name` is unique, so an admin-created group already holding it wins.
    if conn.execute(sa.select(groups_t.c.id).where(groups_t.c.name == to_name)).first():
        return

    conn.execute(
        groups_t.update()
        .where(groups_t.c.system_key == key, groups_t.c.name == from_name)
        .values(name=to_name)
    )
    conn.execute(
        groups_t.update()
        .where(groups_t.c.system_key == key, groups_t.c.description == from_desc)
        .values(description=to_desc)
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not has_column(conn, "permission_groups", "system_key"):
        with op.batch_alter_table("permission_groups") as batch_op:
            batch_op.add_column(
                sa.Column("system_key", sa.String(length=16), nullable=True)
            )
            batch_op.create_index(
                "ix_permission_groups_system_key",
                ["system_key"],
                unique=True,
                if_not_exists=True,
            )

    if has_column(conn, "permission_groups", "is_system"):
        for key, old_name, new_name, _, _ in RENAMES:
            conn.execute(
                groups_t.update()
                .where(
                    groups_t.c.is_system.is_(True),
                    groups_t.c.system_key.is_(None),
                    groups_t.c.name.in_([old_name, new_name]),
                )
                .values(system_key=key)
            )
        with op.batch_alter_table("permission_groups") as batch_op:
            batch_op.drop_column("is_system")

    for key, old_name, new_name, old_desc, new_desc in RENAMES:
        _rename(key, old_name, new_name, old_desc, new_desc)


def downgrade() -> None:
    for key, old_name, new_name, old_desc, new_desc in RENAMES:
        _rename(key, new_name, old_name, new_desc, old_desc)

    with op.batch_alter_table("permission_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
    op.get_bind().execute(
        groups_t.update()
        .where(groups_t.c.system_key.is_not(None))
        .values(is_system=True)
    )

    with op.batch_alter_table("permission_groups") as batch_op:
        batch_op.drop_index("ix_permission_groups_system_key")
        batch_op.drop_column("system_key")
