"""Rename the seeded permission groups to Viewer and Editor

Only the untouched system rows are renamed: a group an admin already renamed
keeps its name, a clash with an existing "Viewer"/"Editor" skips the rename,
and a description the admin edited is kept.

Revision ID: 0135_rename_system_groups
Revises: 0134_gallery_sort_indexes
Create Date: 2026-09-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "0135_rename_system_groups"
down_revision = "0134_gallery_sort_indexes"
branch_labels = None
depends_on = None

# (old name, new name, old description, new description)
RENAMES = (
    (
        "Viewer (legacy)",
        "Viewer",
        "Read the library; manage only your own collections, "
        "assets and devices. Reproduces the pre-upgrade default user.",
        "Read the library; manage only your own collections, assets and devices.",
    ),
    (
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
)


def _rename(from_name: str, to_name: str, from_desc: str, to_desc: str) -> None:
    conn = op.get_bind()
    group_id = conn.execute(
        sa.select(groups_t.c.id).where(
            groups_t.c.name == from_name, groups_t.c.is_system.is_(True)
        )
    ).scalar()
    if group_id is None:
        return
    # `name` is unique, so an admin-created group already holding it wins.
    if conn.execute(sa.select(groups_t.c.id).where(groups_t.c.name == to_name)).first():
        return

    conn.execute(
        groups_t.update().where(groups_t.c.id == group_id).values(name=to_name)
    )
    conn.execute(
        groups_t.update()
        .where(groups_t.c.id == group_id, groups_t.c.description == from_desc)
        .values(description=to_desc)
    )


def upgrade() -> None:
    for old_name, new_name, old_desc, new_desc in RENAMES:
        _rename(old_name, new_name, old_desc, new_desc)


def downgrade() -> None:
    for old_name, new_name, old_desc, new_desc in RENAMES:
        _rename(new_name, old_name, new_desc, old_desc)
