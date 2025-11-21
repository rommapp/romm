"""empty message

Revision ID: 0046_migrate_platform_slugs
Revises: 0045_roms_metadata_update
Create Date: 2025-07-24 15:24:04.331946

"""

import sqlalchemy as sa
from alembic import op

from config.config_manager import config_manager as cm
from handler.metadata.base_handler import UniversalPlatformSlug as UPS

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
        result = connection.execute(
            sa.text(
                "UPDATE platforms SET slug = :new_slug, temp_old_slug = :old_slug WHERE slug = :old_slug"
            ),
            {"new_slug": new_slug.value, "old_slug": old_slug},
        )
        if result.rowcount > 0:
            try:
                cm.add_platform_binding(old_slug, new_slug.value)
            except OSError as e:
                print(
                    f"Error adding platform binding for {old_slug} to {new_slug.value}: {e}"
                )


def downgrade() -> None:
    connection = op.get_bind()
    for old_slug, new_slug in OLD_SLUGS_TO_NEW_MAP.items():
        result = connection.execute(
            sa.text(
                "UPDATE platforms SET slug = temp_old_slug WHERE temp_old_slug = :old_slug AND slug = :new_slug"
            ),
            {"old_slug": old_slug, "new_slug": new_slug.value},
        )
        if result.rowcount > 0:
            try:
                cm.remove_platform_binding(old_slug)
            except OSError as e:
                print(f"Error removing platform binding for {old_slug}: {e}")

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
    "cpc": UPS.ACPC,
    "apple-i": UPS.APPLE,
    "apple2": UPS.APPLEII,
    "apple2gs": UPS.APPLE_IIGS,
    "apple3": UPS.APPLEIII,
    "mattel-aquarius": UPS.AQUARIUS,
    "atari-2600": UPS.ATARI2600,
    "atari-5200": UPS.ATARI5200,
    "atari-7800": UPS.ATARI7800,
    "atari-8-bit": UPS.ATARI8BIT,
    "bally-astrocade": UPS.ASTROCADE,
    "bbc-micro": UPS.BBCMICRO,
    "cd-i": UPS.PHILIPS_CD_I,
    "cdtv": UPS.COMMODORE_CDTV,
    "channel-f": UPS.FAIRCHILD_CHANNEL_F,
    "commodore-16-plus4": UPS.C_PLUS_4,
    "dragon-3264": UPS.DRAGON_32_SLASH_64,
    "dreamcast": UPS.DC,
    "edsac--1": UPS.EDSAC,
    "electron": UPS.ACORN_ELECTRON,
    "elektor-tv-games-computer": UPS.ELEKTOR,
    "fmtowns": UPS.FM_TOWNS,
    "game-com": UPS.GAME_DOT_COM,
    "gameboy": UPS.GB,
    "gameboy-color": UPS.GBC,
    "gameboy-advance": UPS.GBA,
    "game-gear": UPS.GAMEGEAR,
    "gamecube": UPS.NGC,
    "genesis-slash-megadrive": UPS.GENESIS,
    "macintosh": UPS.MAC,
    "microcomputer--1": UPS.MICROCOMPUTER,
    "microvision--1": UPS.MICROVISION,
    "neo-geo": UPS.NEOGEOAES,
    "odyssey--1": UPS.ODYSSEY,
    "nintendo-ds": UPS.NDS,
    "palmos": UPS.PALM_OS,
    "pc88": UPS.PC_8800_SERIES,
    "pc98": UPS.PC_9800_SERIES,
    "pet": UPS.CPET,
    "pdp-7--1": UPS.PDP_7,
    "pdp-8--1": UPS.PDP_8,
    "playstation": UPS.PSX,
    "ps": UPS.PSX,
    "ps4--1": UPS.PS4,
    "playstation-4": UPS.PS4,
    "playstation-5": UPS.PS5,
    "ps-vita": UPS.PSVITA,
    "sega-32x": UPS.SEGA32,
    "sega-cd": UPS.SEGACD,
    "sega-cd-32x": UPS.SEGACD32,
    "sega-master-system": UPS.SMS,
    "sega-saturn": UPS.SATURN,
    "sharp-x1": UPS.X1,
    "sinclair-zx81": UPS.ZX81,
    "sg-1000": UPS.SG1000,
    "switch2": UPS.SWITCH_2,
    "thomson-mo": UPS.THOMSON_MO5,
    "trs-80-coco": UPS.TRS_80_COLOR_COMPUTER,
    "turbografx-16-slash-pc-engine-cd": UPS.TURBOGRAFX_CD,
    "turbo-grafx": UPS.TG16,
    "turbografx16--1": UPS.TG16,
    "watara-slash-quickshot-supervision": UPS.SUPERVISION,
    "windows": UPS.WIN,
    "zx-spectrum": UPS.ZXS,
}
