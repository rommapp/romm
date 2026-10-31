"""Record whether each ROM's sort key is custom

Revision ID: 0157_rom_custom_sort_key_flag
Revises: 0156_roms_platform_min_age_index
Create Date: 2026-10-31 00:00:00.000000

"""

import re

import sqlalchemy as sa
from alembic import op

from utils.database import column_names
from utils.roms_columns import NAME_SORT_KEY_CUSTOM_COLUMN, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0157_rom_custom_sort_key_flag"
down_revision = "0156_roms_platform_min_age_index"
branch_labels = None
depends_on = None

BATCH_SIZE = 1000
# models.rom.compute_name_sort_key when this revision was written: every key
# stored before it was derived by stripping these articles.
LEGACY_ARTICLES = (
    "the",
    "a",
    "an",
    "le",
    "la",
    "les",
    "el",
    "los",
    "las",
    "il",
    "lo",
    "gli",
    "der",
    "die",
    "das",
    "het",
)
LEGACY_ARTICLE_PREFIX_RE = re.compile(rf"^({'|'.join(LEGACY_ARTICLES)})\s+")
DIGIT_RUN_RE = re.compile(r"\d+")
NAME_SORT_KEY_MAX_LENGTH = 500


def _legacy_sort_key(name: str | None) -> str:
    value = (name or "").lower()
    value = LEGACY_ARTICLE_PREFIX_RE.sub("", value).strip()
    value = DIGIT_RUN_RE.sub(lambda m: m.group(0).zfill(12), value)
    return value[:NAME_SORT_KEY_MAX_LENGTH]


def _flag_custom_keys(conn: sa.Connection) -> None:
    """Mark each stored key that no name derives under the legacy rule."""
    roms = sa.table(
        "roms",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("name_sort_key", sa.String),
        sa.column(NAME_SORT_KEY_CUSTOM_COLUMN, sa.Boolean),
    )
    last_id = 0
    while rows := conn.execute(
        sa.select(roms.c.id, roms.c.name, roms.c.name_sort_key)
        .where(roms.c.id > last_id)
        .order_by(roms.c.id)
        .limit(BATCH_SIZE)
    ).all():
        last_id = rows[-1].id
        custom_ids = [
            row.id
            for row in rows
            if row.name_sort_key is not None
            and row.name_sort_key != _legacy_sort_key(row.name)
        ]
        if custom_ids:
            conn.execute(
                sa.update(roms)
                .where(roms.c.id.in_(custom_ids))
                .values({NAME_SORT_KEY_CUSTOM_COLUMN: True})
            )


def upgrade() -> None:
    conn = op.get_bind()
    # An earlier revision's `ensure_roms_columns` may have added the column
    # already, so the flags are filled either way.
    ensure_roms_columns(conn)
    _flag_custom_keys(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if NAME_SORT_KEY_CUSTOM_COLUMN in column_names(conn, "roms"):
        op.drop_column("roms", NAME_SORT_KEY_CUSTOM_COLUMN)
