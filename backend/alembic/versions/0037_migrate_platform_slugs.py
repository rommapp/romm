"""empty message

Revision ID: 0037_migrate_platform_slugs
Revises: 0036_screenscraper_platforms_id
Create Date: 2025-03-01 16:42:16.618676

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0037_migrate_platform_slugs"
down_revision = "0036_screenscraper_platforms_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("url")
        batch_op.drop_column("logo_path")
        batch_op.add_column(
            sa.Column(
                "temp_old_slug",
                sa.String(length=100),
                nullable=True,
            )
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=postgresql.ENUM("VIEWER", "EDITOR", "ADMIN", name="role"),
            nullable=False,
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=False
        )

    # Update slugs already in the database
    connection = op.get_bind()
    for old_slug, new_slug in OLD_SLUGS_TO_NEW_MAP.items():
        connection.execute(
            text(
                f"UPDATE platforms SET slug = '{new_slug}', temp_old_slug = '{old_slug}' WHERE slug = '{old_slug}'"  # trunk-ignore(bandit/B608)
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        text(
            "UPDATE platforms SET slug = temp_old_slug WHERE temp_old_slug IS NOT NULL"
        )
    )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=True
        )
        batch_op.alter_column(
            "role",
            existing_type=postgresql.ENUM("VIEWER", "EDITOR", "ADMIN", name="role"),
            nullable=True,
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("temp_old_slug")
        batch_op.add_column(
            sa.Column("url", sa.String(length=1000), autoincrement=False, nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "logo_path", sa.String(length=1000), autoincrement=False, nullable=True
            )
        )


OLD_SLUGS_TO_NEW_MAP = {
    "1292-advanced-programmable-video-system": "1292apvs",
    "64dd": "n64dd",
    "abc-80": "abc80",
    "acorn-archimedes": "acornarchimedes",
    "acorn-electron": "acornelectron",
    "acpc": "amstradcpc",
    "adventure-vision": "advision",
    "alice-3290": "alice3290",
    "altair-680": "altair680",
    "altair-8800": "altair8800",
    "amazon-alexa": "amazonalexa",
    "amazon-fire-tv": "amazonfiretv",
    "amiga-cd32": "amigacd32",
    "amstrad-pcw": "amstradpcw",
    "apple-i": "apple",
    "apple-iigs": "apple2gs",
    "apple-pippin": "pippin",
    "appleii": "apple2",
    "arcadia-2001": "arcadia",
    "astral-2000": "astral2000",
    "atari-2600": "atari2600",
    "atari-5200": "atari5200",
    "atari-7800": "atari7800",
    "atari-8-bit": "atari8bit",
    "atari-jaguar-cd": "jaguarcd",
    "atari-st": "atarist",
    "atari-vcs": "atarivcs",
    "ay-3-8500": "ay38500",
    "ay-3-8603": "ay38603",
    "ay-3-8605": "ay38605",
    "ay-3-8606": "ay38606",
    "ay-3-8607": "ay38607",
    "ay-3-8610": "ay38610",
    "ay-3-8710": "ay38710",
    "ay-3-8760": "ay38760",
    "bally-astrocade": "astrocade",
    "bbc-micro": "bbcmicro",
    "blu-ray-disc-player": "bluray",
    "blu-ray-player": "bluray",
    "c-plus-4": "cplus4",
    "camputers-lynx": "camplynx",
    "casio-loopy": "loopy",
    "casio-programmable-calculator": "casiocalc",
    "casio-pv-1000": "pv1000",
    "cd-i": "cdi",
    "champion-2711": "champion2711",
    "channel-f": "channelf",
    "commodore-16-plus4": "c16plus4",
    "commodore-cdtv": "cdtv",
    "compucolor-i": "compucolor",
    "compucolor-ii": "compucolor2",
    "compucorp-programmable-calculator": "compucorpcalc",
    "cpc": "amstradcpc",
    "danger-os": "dangeros",
    "dc": "dreamcast",
    "dedicated-console": "dedicatedconsole",
    "dedicated-handheld": "dedicatedhandheld",
    "dragon-32-slash-64": "dragon32",
    "dragon-3264": "dragon32",
    "dvd-player": "dvd",
    "ecd-micromind": "micromind",
    "electron": "acornelectron",
    "epoch-cassette-vision": "ecv",
    "epoch-game-pocket-computer": "egpc",
    "epoch-super-cassette-vision": "scv",
    "exidy-sorcerer": "exidysorcerer",
    "fairchild-channel-f": "channelf",
    "fire-os": "fireos",
    "fm-7": "fm7",
    "fm-towns": "fmtowns",
    "fred-cosmac": "cosmac",
    "g-and-w": "gameandwatch",
    "g-cluster": "gcluster",
    "game-com": "gamecom",
    "game-dot-com": "gamecom",
    "game-gear": "gamegear",
    "game-wave": "gamewave",
    "gameboy": "gb",
    "gameboy-advance": "gba",
    "gameboy-color": "gbc",
    "gamecube": "ngc",
    "gear-vr": "gearvr",
    "genesis": "megadrive",
    "genesis-slash-megadrive": "megadrive",
    "gp2x-wiz": "gp2xwiz",
    "handheld-electronic-lcd": "lcdgames",
    "hd-dvd-player": "hddvd",
    "heathkit-h11": "heathkith11",
    "hitachi-s1": "hitachis1",
    "hp-9800": "hp9800",
    "hp-programmable-calculator": "hpcalc",
    "hyper-neo-geo-64": "hyperneogeo64",
    "ibm-5100": "ibm5100",
    "ideal-computer": "idealcomputer",
    "intel-8008": "intel8008",
    "intel-8080": "intel8080",
    "intel-8086": "intel8086",
    "intellivision-amico": "amico",
    "interact-model-one": "interactm1",
    "interton-video-2000": "intertonv2000",
    "ipod-classic": "ipod",
    "jupiter-ace": "jupiterace",
    "kim-1": "kim1",
    "leapfrog-explorer": "leapsterexplorer",
    "leapster-explorer-slash-leadpad-explorer": "leapsterexplorer",
    "legacy-computer": "legacypc",
    "matsushitapanasonic-jr": "matsushitapanasonicjr",
    "mattel-aquarius": "aquarius",
    "mega-duck-slash-cougar-boy": "megaduck",
    "memotech-mtx": "memotechmtx",
    "meta-quest-2": "quest2",
    "meta-quest-3": "quest3",
    "microtan-65": "microtan65",
    "microvision--1": "microvision",
    "mobile-custom": "mobile",
    "mos-technology-6502": "mos6502",
    "motorola-6800": "motorola6800",
    "motorola-68k": "motorola68k",
    "nec-pc-6000-series": "pc60",
    "neo-geo": "neogeoaes",
    "neo-geo-cd": "neogeocd",
    "neo-geo-pocket": "ngp",
    "neo-geo-pocket-color": "ngpc",
    "neo-geo-x": "neogeox",
    "new-nintendo-3ds": "new3ds",
    "nintendo-ds": "nds",
    "nintendo-dsi": "dsi",
    "noval-760": "noval760",
    "oculus-go": "oculusgo",
    "oculus-quest": "oculusquest",
    "oculus-rift": "oculusrift",
    "odyssey--1": "odyssey",
    "odyssey-2": "odyssey2",
    "odyssey-2-slash-videopac-g7000": "odyssey2",
    "ohio-scientific": "ohiosci",
    "onlive-game-system": "onlive",
    "palm-os": "palmos",
    "panasonic-jungle": "panasonicjungle",
    "panasonic-m2": "panasonicm2",
    "pc-50x-family": "pc50",
    "pc-6001": "pc60",
    "pc-8000": "pc8000",
    "pc-8800-series": "pc88",
    "pc-9800-series": "pc98",
    "pc-booter": "pcbooter",
    "pc-fx": "pcfx",
    "philips-cd-i": "cdi",
    "philips-vg-5000": "vg5000",
    "plato--1": "plato",
    "playstation": "psx",
    "playstation-4": "ps4",
    "playstation-5": "ps5",
    "playstation-now": "psnow",
    "plex-arcade": "plexarcade",
    "plug-and-play": "plugnplay",
    "pokemon-mini": "pokemini",
    "poly-88": "poly88",
    "ps": "psx",
    "ps-vita": "psvita",
    "ps4--1": "ps4",
    "r-zone": "rzone",
    "rca-studio-ii": "rcastudio2",
    "research-machines-380z": "rm380z",
    "sam-coupe": "samcoupe",
    "sd-200270290": "sd200",
    "sega-32x": "sega32x",
    "sega-cd": "segacd",
    "sega-master-system": "sms",
    "sega-pico": "pico",
    "sega-saturn": "saturn",
    "sega32": "sega32x",
    "series-x": "seriesxs",
    "sg-1000": "sg1000",
    "sharp-mz-2200": "mz2200",
    "sharp-x1": "x1",
    "sharp-x68000": "x68000",
    "sharp-zaurus": "zaurus",
    "signetics-2650": "signetics2650",
    "sinclair-ql": "sinclairql",
    "sinclair-zx81": "zx81",
    "sk-vm": "skvm",
    "smc-777": "smc777",
    "sol-20": "sol20",
    "sord-m5": "sordm5",
    "sri-5001000": "sri500",
    "super-acan": "superacan",
    "super-vision-8000": "supervision8000",
    "sure-shot-hd": "sureshothd",
    "swtpc-6800": "swtpc6800",
    "taito-x-55": "x55",
    "tatung-einstein": "tatungeinstein",
    "tektronix-4050": "tektronix4050",
    "tele-spiel": "telespiel",
    "telstar-arcade": "telstar",
    "terebikko-slash-see-n-say-video-phone": "terebikko",
    "thomson-mo": "thomsonmo",
    "thomson-mo5": "thomsonmo",
    "thomson-to": "thomsonto",
    "ti-99": "ti99",
    "ti-994a": "ti99",
    "ti-programmable-calculator": "ticalc",
    "tiki-100": "tiki100",
    "timex-sinclair-2068": "timex2068",
    "tomahawk-f1": "tomahawkf1",
    "tomy-tutor": "tutor",
    "trs-80": "trs80",
    "trs-80-coco": "coco",
    "trs-80-color-computer": "coco",
    "trs-80-mc-10": "trs80mc10",
    "trs-80-model-100": "trs80model100",
    "turbo-grafx": "pcengine",
    "turbografx-16-slash-pc-engine-cd": "pcenginecd",
    "turbografx-cd": "pcenginecd",
    "turbografx16--1": "pcengine",
    "vc-4000": "vc4000",
    "vic-20": "c20",
    "videopac-g7400": "videopacplus",
    "virtual-boy": "virtualboy",
    "visual-memory-unit-slash-visual-memory-system": "vmu",
    "watara-slash-quickshot-supervision": "supervision",
    "wii-u": "wiiu",
    "windows-apps": "windowsapps",
    "windows-mobile": "windowsmobile",
    "windows-phone": "winphone",
    "wonderswan": "wswan",
    "wonderswan-color": "wswanc",
    "xbox-one": "xboxone",
    "xbox-series": "seriesxs",
    "z-machine": "zmachine",
    "zilog-z8000": "z8000",
    "zx-spectrum": "zxs",
    "zx-spectrum-next": "zxsnext",
}
