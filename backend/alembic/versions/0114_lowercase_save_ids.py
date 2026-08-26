"""Lowercase the 3DS, Wii and Wii U save ids stored before sigil emitted them
in the case the emulators write.

Revision ID: 0114_lowercase_save_ids
Revises: 0113_sigil_folder_split
Create Date: 2026-08-26 00:00:00.000000

"""

from collections.abc import Callable

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0114_lowercase_save_ids"
down_revision = "0113_sigil_folder_split"
branch_labels = None
depends_on = None

# Frozen at this revision: a migration describes the rows as they were, so it
# must not follow later edits to SIGIL_PLATFORM_SLUGS.
RECASED_PLATFORM_SLUGS = ("3ds", "wii", "wiiu")

roms = sa.table(
    "roms",
    sa.column("id", sa.Integer),
    sa.column("platform_id", sa.Integer),
    sa.column("save_id", sa.String),
)
rom_files = sa.table(
    "rom_files",
    sa.column("rom_id", sa.Integer),
    sa.column("save_id", sa.String),
)
platforms = sa.table(
    "platforms",
    sa.column("id", sa.Integer),
    sa.column("slug", sa.String),
)


Recase = Callable[[sa.ColumnElement[str]], sa.ColumnElement[str]]


def _recase_save_ids(recase: Recase) -> None:
    recased_platforms = sa.select(platforms.c.id).where(
        platforms.c.slug.in_(RECASED_PLATFORM_SLUGS)
    )
    recased_roms = sa.select(roms.c.id).where(roms.c.platform_id.in_(recased_platforms))

    op.execute(
        roms.update()
        .where(roms.c.platform_id.in_(recased_platforms))
        .where(roms.c.save_id.is_not(None))
        .values(save_id=recase(roms.c.save_id))
    )
    op.execute(
        rom_files.update()
        .where(rom_files.c.rom_id.in_(recased_roms))
        .where(rom_files.c.save_id.is_not(None))
        .values(save_id=recase(rom_files.c.save_id))
    )


def upgrade() -> None:
    _recase_save_ids(sa.func.lower)


def downgrade() -> None:
    # These ids are hex, so uppercasing is an exact inverse.
    _recase_save_ids(sa.func.upper)
