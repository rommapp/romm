"""empty message

Revision ID: 0025_file_hashes_scan
Revises: 0024_sibling_roms_db_view
Create Date: 2024-08-11 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from config import SCAN_TIMEOUT
from endpoints.sockets.scan import scan_platforms
from handler.redis_handler import high_prio_queue
from handler.scan_handler import ScanType

# revision identifiers, used by Alembic.
revision = "0025_file_hashes_scan"
down_revision = "0024_sibling_roms_db_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Run a hash scan in the background
    high_prio_queue.enqueue(
        scan_platforms, [], ScanType.HASH_SCAN, [], [], job_timeout=SCAN_TIMEOUT
    )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DROP VIEW sibling_roms;
            """
        ),
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_igdb_id")
        batch_op.drop_index("idx_roms_moby_id")
