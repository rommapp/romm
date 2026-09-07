"""Add covering index for the sibling_roms self-join

The sibling_roms view self-joins roms on platform_id plus a 7-way OR over
metadata id columns (igdb_id, moby_id, ss_id, launchbox_id, ra_id, hasheous_id,
tgdb_id). When the join is filtered by a parent rom, the OR can't be
index-driven (the compared values come from the joined row, not constants), so
each parent scanned every rom on its platform and read wide rows just to
evaluate the OR. This composite index lets the join seek the platform partition
and resolve the OR from the index alone, without hydrating the wide rows.

Revision ID: 0090_roms_sibling_cover_index
Revises: 0089_client_tokens_device_id
Create Date: 2026-06-24 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0090_roms_sibling_cover_index"
down_revision = "0089_client_tokens_device_id"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_sibling_cover"
INDEX_COLUMNS = [
    "platform_id",
    "igdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "hasheous_id",
    "tgdb_id",
    "id",
]


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
