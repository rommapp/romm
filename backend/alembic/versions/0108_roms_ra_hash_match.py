"""Record whether RetroAchievements knows a ROM's own hash

`ra_id` is the RetroAchievements *game*, and every version of a game resolves
to the same one: on the Hasheous path it comes from the matched game's metadata
list, so a bad dump and a good dump of the same title are indistinguishable by
it. Achievements, though, only unlock when the file's RA hash is in RA's hash
list, which is a per-file fact RomM computed during scans and then threw away.

This column keeps it. NULL means never checked -- no RA hash, a platform RA
doesn't cover, or a ROM last scanned before this existed -- so it stays
distinguishable from a checked-and-absent hash.

Revision ID: 0108_roms_ra_hash_match
Revises: 0107_roms_dedup_cover_index
Create Date: 2026-08-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0108_roms_ra_hash_match"
down_revision = "0107_roms_dedup_cover_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_hash_match", sa.Boolean(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("ra_hash_match", if_exists=True)
