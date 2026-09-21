"""Normalize the region and language values metadata providers wrote

Filename parsing canonicalizes every tag it reads ("usa", "U" and "USA" all
become ``USA``), but the gamelist provider wrote ``<region>`` and ``<lang>``
through verbatim, so a scraped library stores provider shortcodes ("us", "en")
next to canonical names. The two spellings are separate facet values in the
filter drawer, and ``generated_primary_region`` is matched against canonical
names, so a rom whose region reads "us" ranks last in the sibling dedup window
instead of first.

The handler now canonicalizes on the way in. This rewrites the rows already
stored. ``roms_facets`` and ``generated_primary_region`` follow on their own:
the facets mirror is trigger-fed from ``roms`` (0100) and the primary region is
a generated column over ``regions[0]`` (0098).

Revision ID: 0129_normalize_region_language
Revises: 0128_hltb_main_story_column
Create Date: 2026-09-21 00:00:00.000000

"""

from collections.abc import Callable, Iterable
from typing import Any

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# The canonical vocabulary lives with the parser that defines it, so a region
# added there is normalized here too rather than against a stale copy.
from handler.filesystem.base_handler import (
    normalize_provider_languages,
    normalize_provider_regions,
)
from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0129_normalize_region_language"
down_revision = "0128_hltb_main_story_column"
branch_labels = None
depends_on = None

# Pages the rewrite so a scraped library is not read into memory at once.
PAGE_SIZE = 1000

roms_table = sa.table(
    "roms",
    sa.column("id", sa.Integer),
    sa.column("regions", CustomJSON()),
    sa.column("languages", CustomJSON()),
)


def _normalized(value: Any, normalize: Callable[[Iterable[str]], list[str]]) -> Any:
    """Canonicalize a stored list, leaving anything else as it was found."""
    if not isinstance(value, list):
        return value

    return normalize(item for item in value if isinstance(item, str))


def upgrade() -> None:
    connection = op.get_bind()
    update = (
        sa.update(roms_table)
        .where(roms_table.c.id == sa.bindparam("row_id"))
        .values(
            regions=sa.bindparam("new_regions", type_=CustomJSON()),
            languages=sa.bindparam("new_languages", type_=CustomJSON()),
        )
    )

    last_id = 0
    while True:
        page = connection.execute(
            sa.select(roms_table.c.id, roms_table.c.regions, roms_table.c.languages)
            .where(roms_table.c.id > last_id)
            .order_by(roms_table.c.id)
            .limit(PAGE_SIZE)
        ).all()
        if not page:
            break

        last_id = page[-1].id
        params = []
        for row in page:
            regions = _normalized(row.regions, normalize_provider_regions)
            languages = _normalized(row.languages, normalize_provider_languages)
            if regions == row.regions and languages == row.languages:
                continue
            params.append(
                {
                    "row_id": row.id,
                    "new_regions": regions,
                    "new_languages": languages,
                }
            )

        if params:
            connection.execute(update, params)


def downgrade() -> None:
    # The provider shortcode a value was stored as is not recoverable from its
    # canonical name, and nothing reads the old spelling.
    pass
