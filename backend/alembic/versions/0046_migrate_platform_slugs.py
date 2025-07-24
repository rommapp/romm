"""empty message

Revision ID: 0046_migrate_platform_slugs
Revises: 0045_roms_metadata_update
Create Date: 2025-07-24 15:24:04.331946

"""

import sqlalchemy as sa
from alembic import op

revision = "0046_migrate_platform_slugs"
down_revision = "0045_roms_metadata_update"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("temp_old_slug", sa.String(length=100), nullable=True)
        )
        batch_op.drop_column("logo_path")

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DATETIME(),
            type_=sa.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DATETIME(),
            type_=sa.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "fs_name", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_name_no_tags", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_name_no_ext", existing_type=sa.VARCHAR(length=450), nullable=False
        )
        batch_op.alter_column(
            "fs_extension", existing_type=sa.VARCHAR(length=100), nullable=False
        )
        batch_op.alter_column(
            "fs_path", existing_type=sa.VARCHAR(length=1000), nullable=False
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role", existing_type=sa.Enum("VIEWER", "EDITOR", "ADMIN"), nullable=False
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=False
        )
        batch_op.alter_column(
            "ra_username",
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=255),
            existing_nullable=True,
        )

    # Update slugs already in the database
    connection = op.get_bind()
    for old_slug, new_slug in OLD_SLUGS_TO_NEW_MAP.items():
        connection.execute(
            sa.text(
                "UPDATE platforms SET slug = :new_slug, temp_old_slug = :old_slug WHERE slug = :old_slug"
            ),
            {"new_slug": new_slug, "old_slug": old_slug},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE platforms SET slug = temp_old_slug WHERE temp_old_slug IS NOT NULL"
        )
    )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "ra_username",
            existing_type=sa.String(length=255),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=True
        )
        batch_op.alter_column(
            "role", existing_type=sa.Enum("VIEWER", "EDITOR", "ADMIN"), nullable=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "fs_path", existing_type=sa.VARCHAR(length=1000), nullable=True
        )
        batch_op.alter_column(
            "fs_extension", existing_type=sa.VARCHAR(length=100), nullable=True
        )
        batch_op.alter_column(
            "fs_name_no_ext", existing_type=sa.VARCHAR(length=450), nullable=True
        )
        batch_op.alter_column(
            "fs_name_no_tags", existing_type=sa.VARCHAR(length=450), nullable=True
        )
        batch_op.alter_column(
            "fs_name", existing_type=sa.VARCHAR(length=450), nullable=True
        )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.TIMESTAMP(timezone=True),
            type_=sa.DATETIME(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.TIMESTAMP(timezone=True),
            type_=sa.DATETIME(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("logo_path", sa.VARCHAR(length=1000), nullable=True)
        )
        batch_op.drop_column("temp_old_slug")


OLD_SLUGS_TO_NEW_MAP = {
    "cpc": "acpc",
    "apple-i": "apple",
    "apple2": "appleii",
    "apple2gs": "apple-iigs",
    "apple3": "appleiii",
    "aquarius": "mattel-aquarius",
    "atari-2600": "atari2600",
    "atari-5200": "atari5200",
    "atari-7800": "atari7800",
    "atari-8-bit": "atari8bit",
    "bally-astrocade": "astrocade",
    "bbc-micro": "bbcmicro",
    "cd-i": "philips-cd-i",
    "cdtv": "commodore-cdtv",
    "channel-f": "fairchild-channel-f",
    "commodore-16-plus4": "c-plus-4",
    "dragon-3264": "dragon-32-slash-64",
    "dreamcast": "dc",
    "edsac--1": "edsac",
    "electron": "acorn-electron",
    "elektor-tv-games-computer": "elektor",
    "fmtowns": "fm-towns",
    "game-com": "game-dot-com",
    "gameboy": "gb",
    "gameboy-color": "gbc",
    "gameboy-advance": "gba",
    "game-gear": "gamegear",
    "gamecube": "ngc",
    "genesis-slash-megadrive": "genesis",
    "macintosh": "mac",
    "microcomputer--1": "microcomputer",
    "microvision--1": "microvision",
    "neo-geo": "neogeoaes",
    "odyssey--1": "odyssey",
    "nintendo-ds": "nds",
    "palmos": "palm-os",
    "pc88": "pc-8800-series",
    "pc98": "pc-9800-series",
    "pet": "cpet",
    "pdp-7--1": "pdp-7",
    "pdp-8--1": "pdp-8",
    "playstation": "psx",
    "ps": "psx",
    "ps4--1": "ps4",
    "playstation-4": "ps4",
    "playstation-5": "ps5",
    "ps-vita": "psvita",
    "sega-32x": "sega32",
    "sega-cd": "segacd",
    "sega-master-system": "sms",
    "sega-saturn": "saturn",
    "sharp-x1": "x1",
    "sinclair-zx81": "zx81",
    "sg-1000": "sg1000",
    "switch2": "switch-2",
    "thomson-mo": "thomson-mo5",
    "trs-80-coco": "trs-80-color-computer",
    "turbografx-16-slash-pc-engine-cd": "turbografx-cd",
    "turbo-grafx": "tg16",
    "turbografx16--1": "tg16",
    "watara-slash-quickshot-supervision": "supervision",
    "windows": "win",
}
