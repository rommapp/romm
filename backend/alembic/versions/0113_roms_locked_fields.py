"""Record which rom fields a user supplied by hand

Uploading artwork stores the file and clears `url_cover`, so a stored cover
path with no url was the only thing separating a hand-supplied cover from a
scraped one. That signal cannot survive: `get_cover` returns no path when the
file is missing, and the scan writes that straight back to `path_cover_s`, so a
single scan run while the resources volume is unavailable erases it. The next
scan then reads the row as having no cover at all, adopts the provider url, and
replaces the user's cover with provider art once storage returns.

`locked_fields` records the same fact durably, independent of what is on disk.

The backfill is the load-bearing part: existing uploads are recognisable only by
the old inferred marker, and reading it once here is the last chance to do so.
Without it the first scan after upgrading would replace every uploaded cover in
every library.

Manuals are deliberately not backfilled. An uploaded manual and a scraped one
share a path and neither clears `url_manual`, so nothing distinguishes them and
any guess would be wrong for half the rows. Manuals stay pinned by the scan, and
uploads made from here on are marked as they happen.

Revision ID: 0113_roms_locked_fields
Revises: 0112_publisher_developer_split
Create Date: 2026-08-08 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0113_roms_locked_fields"
down_revision = "0112_publisher_developer_split"
branch_labels = None
depends_on = None


def _roms_table() -> sa.TableClause:
    return sa.table(
        "roms",
        sa.column("path_cover_s", sa.Text),
        sa.column("url_cover", sa.Text),
        sa.column("locked_fields", CustomJSON()),
    )


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("locked_fields", CustomJSON(), nullable=True),
            if_not_exists=True,
        )

    roms = _roms_table()
    connection = op.get_bind()

    # A stored cover path with an empty url is the pre-migration marker for an
    # upload.
    connection.execute(
        roms.update()
        .where(
            sa.and_(
                roms.c.path_cover_s.isnot(None),
                roms.c.path_cover_s != "",
                sa.or_(roms.c.url_cover.is_(None), roms.c.url_cover == ""),
            )
        )
        .values(locked_fields=["url_cover"])
    )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("locked_fields", if_exists=True)
