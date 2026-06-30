"""Drop stored ScreenScraper media download URLs

ScreenScraper media URLs were saved into roms.ss_metadata (the ``*_url`` entries)
and into url_cover / url_manual / url_screenshots during a scan, even though the
assets are downloaded to local files (``*_path``) that the UI renders from. The
stored URLs are SS API queries (carrying auth params, re-derivable from the
stored ss_id) and are never read after the download, so this migration removes
them from existing rows (issue #3612):

- drop every ``*_url`` key from ss_metadata
- blank url_cover / url_manual and drop screenshot entries that point at
  ScreenScraper; other providers' public URLs are left untouched as they are
  valid cover fallbacks

The per-asset change-detection tags (ss_metadata.cover_media, etc.) are not
back-filled here as they cannot be derived without re-querying ScreenScraper;
the next scan repopulates them.

Revision ID: 0092_strip_ss_media_urls
Revises: 0091_unique_platform_fs_name
Create Date: 2026-06-26 00:00:00.000000

"""

from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0092_strip_ss_media_urls"
down_revision = "0091_unique_platform_fs_name"
branch_labels = None
depends_on = None

BATCH_SIZE = 1000

roms_table = sa.table(
    "roms",
    sa.column("id", sa.Integer),
    sa.column("ss_metadata", CustomJSON()),
    sa.column("url_cover", sa.Text),
    sa.column("url_manual", sa.Text),
    sa.column("url_screenshots", CustomJSON()),
)


def _is_screenscraper_url(url: object) -> bool:
    if not isinstance(url, str) or not url:
        return False
    try:
        host = urlparse(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.lower()
    return host == "screenscraper.fr" or host.endswith(".screenscraper.fr")


def _clean_ss_metadata(ss_metadata: object) -> object:
    """Return ss_metadata without any media download URL (``*_url``) keys."""
    if not isinstance(ss_metadata, dict):
        return ss_metadata
    return {
        key: value for key, value in ss_metadata.items() if not key.endswith("_url")
    }


def upgrade() -> None:
    connection = op.get_bind()

    last_id = 0
    while True:
        rows = connection.execute(
            sa.select(
                roms_table.c.id,
                roms_table.c.ss_metadata,
                roms_table.c.url_cover,
                roms_table.c.url_manual,
                roms_table.c.url_screenshots,
            )
            .where(roms_table.c.id > last_id)
            .order_by(roms_table.c.id)
            .limit(BATCH_SIZE)
        ).all()
        if not rows:
            break

        for row in rows:
            updates: dict = {}

            if isinstance(row.ss_metadata, dict):
                cleaned_meta = _clean_ss_metadata(row.ss_metadata)
                if cleaned_meta != row.ss_metadata:
                    updates["ss_metadata"] = cleaned_meta

            if _is_screenscraper_url(row.url_cover):
                updates["url_cover"] = ""

            if _is_screenscraper_url(row.url_manual):
                updates["url_manual"] = ""

            if isinstance(row.url_screenshots, list):
                kept_shots = [
                    shot
                    for shot in row.url_screenshots
                    if not _is_screenscraper_url(shot)
                ]
                if kept_shots != row.url_screenshots:
                    updates["url_screenshots"] = kept_shots

            if updates:
                connection.execute(
                    sa.update(roms_table)
                    .where(roms_table.c.id == row.id)
                    .values(**updates)
                )

        last_id = rows[-1].id


def downgrade() -> None:
    # Irreversible: the dropped URLs and *_url entries cannot be reconstructed.
    # The downloaded local assets remain valid, so this is a no-op.
    pass
