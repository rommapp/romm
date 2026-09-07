"""Add composite index on states (rom_id, user_id)

The "has save states" gallery filter runs a correlated EXISTS scoped to the
current user (states.rom_id = roms.id AND states.user_id = ?). The states table
only had the auto FK index on rom_id, so that predicate could not be resolved
from an index alone. This composite lets the EXISTS seek directly. The saves
table already has an equivalent leftmost prefix via ix_saves_rom_user_hash.

Revision ID: 0093_states_rom_user_index
Revises: 0092_permission_system
Create Date: 2026-07-01 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0093_states_rom_user_index"
down_revision = "0092_permission_system"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_states_rom_user"
INDEX_COLUMNS = ["rom_id", "user_id"]


def upgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
