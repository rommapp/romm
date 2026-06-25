"""Narrow the user role vocabulary from viewer/editor/admin to user/admin.

The viewer/editor distinction now lives entirely in permission groups, so the
`role` column collapses to two kinds: `admin` (bypasses everything) and `user`.

The column is converted from a native enum to a portable VARCHAR (matching the
rest of the permission vocabulary, `native_enum=False`) and existing values are
normalized: ADMIN -> admin, VIEWER/EDITOR -> user. Stored values are lowercase.

Revision ID: 0092_narrow_role_to_admin_user
Revises: 0091_permission_system
Create Date: 2026-06-25 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0092_narrow_role_to_admin_user"
down_revision = "0091_permission_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the native 3-value enum in favour of a plain VARCHAR so the
    # vocabulary can change without a destructive cross-dialect ALTER TYPE.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum("VIEWER", "EDITOR", "ADMIN", name="role"),
            type_=sa.String(length=20),
            existing_nullable=False,
        )

    # Collapse to the two-value lowercase vocabulary. UPPER() guards against
    # either casing being present (native enums stored the uppercase name).
    op.execute("UPDATE users SET role = 'admin' WHERE UPPER(role) = 'ADMIN'")
    op.execute(
        "UPDATE users SET role = 'user' "
        "WHERE UPPER(role) IN ('VIEWER', 'EDITOR', 'USER') OR role IS NULL"
    )


def downgrade() -> None:
    # Best-effort reverse: map user -> viewer, keep admin, restore the enum.
    op.execute("UPDATE users SET role = 'VIEWER' WHERE LOWER(role) = 'user'")
    op.execute("UPDATE users SET role = 'ADMIN' WHERE LOWER(role) = 'admin'")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=20),
            type_=sa.Enum("VIEWER", "EDITOR", "ADMIN", name="role"),
            existing_nullable=False,
        )
