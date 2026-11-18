"""Rename the PICO-8 slug and fold duplicate slugs into the platform they name

Revision ID: 0162_merge_platform_slugs
Revises: 0161_save_channels
Create Date: 2026-11-18 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from config.config_manager import Config
from config.config_manager import config_manager as cm
from exceptions.config_exceptions import ConfigNotWritableException

revision = "0162_merge_platform_slugs"
down_revision = "0161_save_channels"
branch_labels = None
depends_on = None

PICO_8_OLD_SLUG = "pico"
PICO_8_SLUG = "pico-8"
# The names and binding rule that resolve to PICO-8 at this revision, frozen
# against later alias edits.
PICO_8_NAMES = frozenset({PICO_8_SLUG, "pico8"})

# Each old slug and the slug that replaces it.
OLD_SLUGS_TO_NEW = {
    PICO_8_OLD_SLUG: PICO_8_SLUG,
    "famicom": "nes",
    "sfam": "snes",
    "atari800": "atari8bit",
    "pc-6001": "nec-pc-6000-series",
    "vmu": "visual-memory-unit-slash-visual-memory-system",
}


def _pico_8_folders(connection: sa.Connection) -> list[str]:
    rows = connection.execute(
        sa.text("SELECT fs_slug FROM platforms WHERE LOWER(slug) = :slug"),
        {"slug": PICO_8_OLD_SLUG},
    )
    return [fs_slug for (fs_slug,) in rows]


def _resolved_name(fs_slug: str, config: Config) -> str:
    """The name a folder resolves through: its binding, its version, or itself."""
    key = fs_slug.lower()
    bound = config.PLATFORMS_BINDING.get(key) or config.PLATFORMS_VERSIONS.get(key)
    return (bound or fs_slug).lower()


def _bind(fs_slug: str, slug: str) -> None:
    try:
        cm.add_platform_binding(fs_slug, slug)
    except (OSError, ConfigNotWritableException) as e:
        print(f"Error binding {fs_slug} to {slug}, add it to config.yml: {e}")


def upgrade() -> None:
    connection = op.get_bind()
    config = cm.get_config()

    # `pico` now names the Sega Pico, so keep these folders filed as PICO-8.
    for fs_slug in _pico_8_folders(connection):
        if _resolved_name(fs_slug, config) not in PICO_8_NAMES:
            _bind(fs_slug, PICO_8_SLUG)

    for old_slug, new_slug in OLD_SLUGS_TO_NEW.items():
        connection.execute(
            sa.text(
                "UPDATE platforms SET slug = :new_slug, temp_old_slug = :old_slug "
                "WHERE LOWER(slug) = :old_slug"
            ),
            {"new_slug": new_slug, "old_slug": old_slug},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for old_slug, new_slug in OLD_SLUGS_TO_NEW.items():
        connection.execute(
            sa.text(
                "UPDATE platforms SET slug = temp_old_slug "
                "WHERE temp_old_slug = :old_slug AND slug = :new_slug"
            ),
            {"old_slug": old_slug, "new_slug": new_slug},
        )

    config = cm.get_config()
    for fs_slug in _pico_8_folders(connection):
        if config.PLATFORMS_BINDING.get(fs_slug.lower()) != PICO_8_SLUG:
            continue
        # A folder named pico resolves to it unbound; any other was bound to it.
        if fs_slug.lower() != PICO_8_OLD_SLUG:
            _bind(fs_slug, PICO_8_OLD_SLUG)
            continue
        try:
            cm.remove_platform_binding(fs_slug)
        except (OSError, ConfigNotWritableException) as e:
            print(f"Error removing the {PICO_8_SLUG} binding for {fs_slug}: {e}")
