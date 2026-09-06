from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fastapi import Request

from config.config_manager import PLATFORM_MEDIA_DIRS
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler, fs_resource_handler
from logger.logger import log
from models.platform import Platform
from models.rom import HAS_FILE_ON_DISK_FILTERS, Rom
from utils.filesystem import link_or_copy_file
from utils.platform_slugs import UniversalPlatformSlug as UPS

# Map RomM platform slugs to canonical Pegasus (collection name, shortname) pairs.
# Source: https://www.pegasus-frontend.org/docs/user-guide/meta-files/
# Only platforms present in the official Pegasus "Common platform names" table are listed.
SLUG_TO_PEGASUS: dict[UPS, tuple[str, str]] = {
    # Atari
    UPS.ATARI2600: ("Atari 2600", "atari2600"),
    UPS.ATARI5200: ("Atari 5200", "atari5200"),
    UPS.ATARI7800: ("Atari 7800", "atari7800"),
    UPS.ATARI800: ("Atari 800", "atari800"),
    UPS.ATARI_JAGUAR_CD: ("Atari Jaguar CD", "atarijaguarcd"),
    UPS.JAGUAR: ("Atari Jaguar", "atarijaguar"),
    UPS.LYNX: ("Atari Lynx", "atarilynx"),
    UPS.ATARI_ST: ("Atari ST", "atarist"),
    UPS.ATARI_XEGS: ("Atari XE", "atarixe"),
    # Nintendo handhelds
    UPS.GB: ("Game Boy", "gb"),
    UPS.GBC: ("Game Boy Color", "gbc"),
    UPS.GBA: ("Game Boy Advance", "gba"),
    UPS.NDS: ("Nintendo DS", "nds"),
    UPS.N3DS: ("Nintendo 3DS", "3ds"),
    UPS.G_AND_W: ("Nintendo Game-and-Watch", "gameandwatch"),
    UPS.VIRTUALBOY: ("Nintendo VirtualBoy", "virtualboy"),
    # Nintendo home consoles
    UPS.NES: ("Nintendo Entertainment System", "nes"),
    UPS.FAMICOM: ("Nintendo Entertainment System", "nes"),
    UPS.FDS: ("Famicom Disk System", "fds"),
    UPS.SNES: ("Super Nintendo Entertainment System", "snes"),
    UPS.SFAM: ("Super Nintendo Entertainment System", "snes"),
    UPS.N64: ("Nintendo 64", "n64"),
    UPS.NGC: ("Nintendo GameCube", "gc"),
    UPS.WII: ("Nintendo Wii", "wii"),
    UPS.WIIU: ("Nintendo WiiU", "wiiu"),
    UPS.SWITCH: ("Nintendo Switch", "switch"),
    # Sega
    UPS.SG1000: ("SEGA SG-1000", "sg1000"),
    UPS.SMS: ("Sega Master System", "mastersystem"),
    UPS.GENESIS: ("Sega Genesis", "genesis"),
    UPS.SEGACD: ("SEGA CD", "segacd"),
    UPS.SEGA32: ("SEGA 32X", "sega32x"),
    UPS.SEGACD32: ("SEGA CD 32X", "sega32x"),
    UPS.SATURN: ("Sega Saturn", "saturn"),
    UPS.DC: ("Sega Dreamcast", "dreamcast"),
    UPS.GAMEGEAR: ("SEGA GameGear", "gamegear"),
    # Sony
    UPS.PSX: ("PlayStation", "psx"),
    UPS.PS2: ("PlayStation 2", "ps2"),
    UPS.PS3: ("PlayStation 3", "ps3"),
    UPS.PSP: ("PlayStation Portable", "psp"),
    UPS.PSVITA: ("PlayStation Vita", "psvita"),
    # Microsoft
    UPS.XBOX: ("Xbox", "xbox"),
    UPS.XBOX360: ("Xbox 360", "xbox360"),
    # NEC / PC Engine
    UPS.TG16: ("TurboGrafx 16", "turbografx16"),
    UPS.TURBOGRAFX_CD: ("PC Engine CD", "pcengine"),
    UPS.PC_FX: ("PC-FX", "pcfx"),
    # SNK Neo Geo
    UPS.NEOGEOAES: ("Neo Geo", "neogeo"),
    UPS.NEOGEOMVS: ("Neo Geo", "neogeo"),
    UPS.NEO_GEO_CD: ("Neo Geo CD", "neogeocd"),
    UPS.NEO_GEO_POCKET: ("Neo Geo Pocket", "ngp"),
    UPS.NEO_GEO_POCKET_COLOR: ("Neo Geo Pocket Color", "ngpc"),
    # Commodore / Amiga
    UPS.AMIGA: ("Amiga", "amiga"),
    UPS.AMIGA_CD32: ("Amiga CD32", "amigacd32"),
    UPS.COMMODORE_CDTV: ("Amiga CDTV", "amigacdtv"),
    UPS.C64: ("Commodore 64", "c64"),
    # Amstrad / Sharp / other home computers
    UPS.ACPC: ("Amstrad CPC", "amstradcpc"),
    UPS.SHARP_X68000: ("Sharp X68000", "x68000"),
    UPS.MSX: ("MSX", "msx"),
    UPS.DOS: ("DOS", "dos"),
    UPS.PC_BOOTER: ("PC", "pc"),
    UPS.LINUX: ("Linux", "linux"),
    UPS.MAC: ("Macintosh", "macintosh"),
    UPS.ANDROID: ("Android", "android"),
    UPS.WIN: ("Windows", "windows"),
    # Arcade
    UPS.ARCADE: ("Arcade", "arcade"),
    # Other consoles / platforms
    UPS._3DO: ("3DO", "3do"),
    UPS.APPLEII: ("Apple II", "apple2"),
    UPS.COLECOVISION: ("ColecoVision", "colecovision"),
    UPS.INTELLIVISION: ("Intellivision", "intellivision"),
    UPS.ODYSSEY_2: ("Odyssey 2", "odyssey2"),
    UPS.VECTREX: ("Vectrex", "vectrex"),
    UPS.SUPERGRAFX: ("SuperGrafx", "supergrafx"),
    UPS.SAM_COUPE: ("SAM coupe", "samcoupe"),
    UPS.SCUMMVM: ("Scumm VM", "scummvm"),
    UPS.TIC_80: ("TIC80", "tic80"),
    UPS.DRAGON_32_SLASH_64: ("Dragon 32", "dragon32"),
    # PC-88 / PC-98
    UPS.PC_8800_SERIES: ("PC 88", "pc88"),
    UPS.PC_9800_SERIES: ("PC 98", "pc98"),
    # WonderSwan
    UPS.WONDERSWAN: ("WonderSwan", "wonderswan"),
    UPS.SWANCRYSTAL: ("WonderSwan/Color", "wonderswancolor"),
    # ZX Spectrum / ZX81
    UPS.ZXS: ("ZX Spectrum", "zxspectrum"),
    UPS.ZX81: ("ZX81", "zx81"),
    UPS.STEAM: ("Steam", "steam"),
}

# Pegasus resolves media from the paths written in metadata.pegasus.txt, so its
# files share the ES-DE media folders instead of a parallel assets/ tree. ES-DE
# keeps logos under marquees.
PEGASUS_MEDIA_KEYS: Final[dict[str, str]] = {
    "box_front": "box2d",
    "box_back": "box2d_back",
    "box_full": "box3d",
    "screenshot": "screenshot",
    "titlescreen": "title_screen",
    "video": "video",
    "marquee": "marquee",
    "logo": "marquee",
    "cartridge": "physical",
    "background": "fanart",
    "bezel": "bezel",
}


# Pegasus accepts several spellings for one field; entries are merged by the
# canonical name so RomM's `file` also replaces an existing `files` list.
PEGASUS_KEY_ALIASES: Final[dict[str, str]] = {
    "files": "file",
    "command": "launch",
    "cwd": "workdir",
    "sort_by": "sort-by",
    "sort-name": "sort-by",
    "sort-title": "sort-by",
    "sort_name": "sort-by",
    "sort_title": "sort-by",
    "sortby": "sort-by",
    "sortname": "sort-by",
    "sorttitle": "sort-by",
    "developers": "developer",
    "publishers": "publisher",
    "genres": "genre",
    "tags": "tag",
}

# Pegasus's own asset-name spellings, folded to the names RomM emits (lowercase
# because keys are lowercased before lookup).
PEGASUS_ASSET_ALIASES: Final[dict[str, str]] = {
    "boxfront": "box_front",
    "boxart2d": "box_front",
    "boxback": "box_back",
    "boxspine": "box_spine",
    "boxside": "box_spine",
    "box_side": "box_spine",
    "boxfull": "box_full",
    "box": "box_full",
    "disc": "cartridge",
    "cart": "cartridge",
    "wheel": "logo",
    "screenmarquee": "bezel",
    "border": "bezel",
    "cabinetleft": "cabinet_left",
    "cabinetright": "cabinet_right",
    "steam": "steamgrid",
    "grid": "steamgrid",
    "flyer": "poster",
    "screenshots": "screenshot",
    "videos": "video",
}

COLLECTION_HEADER_KEYS: Final = frozenset({"collection", "shortname"})


def canonical_pegasus_key(key: str) -> str:
    """Fold every spelling Pegasus accepts for a lowercased key into one name."""
    prefix, dot, asset = key.partition(".")
    if dot and prefix in ("asset", "assets"):
        return f"assets.{PEGASUS_ASSET_ALIASES.get(asset, asset)}"
    return PEGASUS_KEY_ALIASES.get(key, key)


@dataclass
class PegasusBlock:
    """A `collection:` or `game:` block of metadata.pegasus.txt, kept as raw lines.

    ``fields`` pairs each canonical key with the lines that spell it out,
    continuation lines included. Comment lines carry an empty key.
    """

    kind: str
    fields: list[tuple[str, list[str]]] = field(default_factory=list)

    def keys(self) -> set[str]:
        return {key for key, _ in self.fields if key}

    def lines(self, skip: frozenset[str] | set[str] = frozenset()) -> list[str]:
        return [line for key, lines in self.fields if key not in skip for line in lines]

    def file_names(self) -> set[str]:
        """Each listed filename, plus its top folder (a multi-file ROM's fs_name)."""
        names: set[str] = set()
        for key, lines in self.fields:
            if key != "file":
                continue
            _, _, value = lines[0].partition(":")
            for raw in [value, *lines[1:]]:
                if not raw.strip():
                    continue
                path = Path(raw.strip().removeprefix("./"))
                names.add(path.name)
                if len(path.parts) > 1 and not path.is_absolute():
                    names.add(path.parts[0])
        return names


def parse_pegasus(content: str) -> list[PegasusBlock]:
    """Split metadata.pegasus.txt into blocks, the first holding any preamble."""
    blocks = [PegasusBlock("preamble")]
    for line in content.splitlines():
        if not line.strip():
            continue
        if line[0].isspace():
            if blocks[-1].fields:
                blocks[-1].fields[-1][1].append(line)
            continue
        if line.startswith("#"):
            blocks[-1].fields.append(("", [line]))
            continue

        raw_key, separator, _ = line.partition(":")
        key = canonical_pegasus_key(raw_key.strip().lower()) if separator else ""
        if key in ("collection", "game"):
            blocks.append(PegasusBlock(key))
        blocks[-1].fields.append((key, [line]))
    return blocks


@dataclass
class ExistingPegasus:
    """What an on-disk metadata.pegasus.txt holds that RomM did not generate."""

    preamble: list[str] = field(default_factory=list)
    header: PegasusBlock | None = None
    games: list[PegasusBlock] = field(default_factory=list)
    tail: list[PegasusBlock] = field(default_factory=list)


def parse_existing_pegasus(content: str) -> ExistingPegasus:
    """Take apart the first collection of a metadata file; later ones stay verbatim."""
    existing = ExistingPegasus()
    blocks = parse_pegasus(content)
    existing.preamble = blocks[0].lines()

    for index, block in enumerate(blocks[1:], start=1):
        if block.kind == "collection" and existing.header is not None:
            existing.tail = blocks[index:]
            break
        if block.kind == "collection":
            existing.header = block
        else:
            existing.games.append(block)

    return existing


class PegasusExporter:
    """Export RomM collections to Pegasus Frontend metadata.pegasus.txt format"""

    def __init__(self, local_export: bool = False):
        self.local_export = local_export

    @staticmethod
    def _resolve_collection(platform: Platform) -> tuple[str, str]:
        """Return (collection_name, shortname) for a platform."""
        if platform.slug in SLUG_TO_PEGASUS:
            return SLUG_TO_PEGASUS[UPS(platform.slug)]

        return (platform.custom_name or platform.name, platform.slug)

    def _format_release_date(self, timestamp: int) -> str:
        """Format release date to YYYY-MM-DD format"""
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime("%Y-%m-%d")

    def _format_rating(self, average_rating: float) -> str:
        """Format rating as percentage (0-100%). Input is on 0-10 scale."""
        clamped_rating = max(0, min(100, average_rating))
        return f"{int(clamped_rating)}%"

    def _escape_multiline(self, text: str) -> str:
        """Indent continuation lines for multi-line values in Pegasus format"""
        lines = text.strip().splitlines()
        if len(lines) <= 1:
            return text.strip()
        return (
            lines[0]
            + "\n"
            + "\n".join(f"  {line}" if line.strip() else "  ." for line in lines[1:])
        )

    def _collect_assets(self, rom: Rom) -> dict[str, Path]:
        """Collect available media assets for a ROM using model properties.

        Returns a dict mapping Pegasus asset key to the absolute source file path.
        """
        assets: dict[str, Path] = {}

        if rom.path_cover_l:
            assets["box_front"] = fs_resource_handler.validate_path(rom.path_cover_l)

        if rom.path_screenshots:
            assets["screenshot"] = fs_resource_handler.validate_path(
                rom.path_screenshots[0]
            )

        if rom.path_video:
            assets["video"] = fs_resource_handler.validate_path(rom.path_video)

        # Extended media from screenscraper / gamelist metadata
        ss = rom.ss_metadata or {}
        gl = rom.gamelist_metadata or {}

        extended: dict[str, list[str]] = {
            "box_full": [ss.get("box3d_path", ""), gl.get("box3d_path", "")],
            "box_back": [ss.get("box2d_back_path", ""), gl.get("box2d_back_path", "")],
            "logo": [ss.get("logo_path", "")],
            "marquee": [gl.get("marquee_path", "")],
            "cartridge": [ss.get("physical_path", ""), gl.get("physical_path", "")],
            "background": [ss.get("fanart_path", ""), gl.get("fanart_path", "")],
            "titlescreen": [
                ss.get("title_screen_path", ""),
                gl.get("title_screen_path", ""),
            ],
            "bezel": [ss.get("bezel_path", "")],
        }

        for pegasus_key, candidates in extended.items():
            if pegasus_key in assets:
                continue
            for candidate in candidates:
                if candidate:
                    assets[pegasus_key] = fs_resource_handler.validate_path(candidate)
                    break

        return assets

    def _create_game_entry(
        self,
        rom: Rom,
        request: Request | None,
        exported_assets: dict[str, str] | None = None,
    ) -> str:
        """Create a game entry for a ROM in Pegasus metadata format"""
        lines: list[str] = []

        # Game title (required)
        lines.append(f"game: {rom.name or rom.fs_name}")

        # File path
        if self.local_export:
            lines.append(f"file: {rom.fs_name}")
        else:
            if request is None:
                raise ValueError(
                    "Request object must be provided for non-local exports"
                )
            lines.append(
                f"file: {request.url_for('get_rom_content', id=rom.id, file_name=rom.fs_name)}"
            )

        # Sort title (use fs_name_no_tags if different from name)
        if rom.name and rom.fs_name_no_tags and rom.name != rom.fs_name_no_tags:
            lines.append(f"sort-by: {rom.fs_name_no_tags}")

        if rom.metadatum:
            developer = rom.metadatum.primary_developer
            publisher = rom.metadatum.primary_publisher
            if developer:
                lines.append(f"developer: {developer}")
            if publisher:
                lines.append(f"publisher: {publisher}")

        # Genres
        if rom.metadatum and rom.metadatum.genres:
            for genre in rom.metadatum.genres:
                lines.append(f"genre: {genre}")

        # Tags (rom tags like region, language info)
        if rom.tags:
            for tag in rom.tags:
                lines.append(f"tag: {tag}")

        # Player count
        if rom.metadatum and rom.metadatum.player_count:
            lines.append(f"players: {rom.metadatum.player_count}")

        # Summary / description
        if rom.summary:
            lines.append(f"description: {self._escape_multiline(rom.summary)}")

        # Release date
        if rom.metadatum and rom.metadatum.first_release_date is not None:
            lines.append(
                f"release: {self._format_release_date(rom.metadatum.first_release_date)}"
            )

        # Rating
        if rom.metadatum and rom.metadatum.average_rating is not None:
            lines.append(f"rating: {self._format_rating(rom.metadatum.average_rating)}")

        # Asset references (relative paths to asset files)
        if exported_assets:
            for asset_key, rel_path in exported_assets.items():
                lines.append(f"assets.{asset_key}: {rel_path}")

        # RomM-specific extensions (x-* fields)
        if rom.regions:
            lines.append(f"x-region: {', '.join(rom.regions)}")

        if rom.languages:
            lines.append(f"x-language: {', '.join(rom.languages)}")

        lines.append(f"x-romm-id: {rom.id}")

        return "\n".join(lines)

    def _copy_asset(self, source: Path, dest: Path) -> bool:
        """Place ``source`` at ``dest`` via hardlink (same filesystem) or copy
        (otherwise). Returns True on success."""
        if dest.exists():
            return True

        # Metadata scanned before unfetched media paths were cleared can still
        # point at files that were never downloaded.
        if not source.is_file():
            log.debug(f"Skipping asset {source}: source file is missing")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            link_or_copy_file(source, dest)
            return True
        except OSError as e:
            log.warning(f"Failed to copy {source} -> {dest}: {e}")
            return False

    def _build_pegasus(
        self,
        platform_id: int,
        request: Request | None,
        platform_dir: Path | None,
        existing: ExistingPegasus | None = None,
    ) -> tuple[str, int]:
        """Build the metadata file, optionally copying media under ``platform_dir``.

        Entries in ``existing`` keep whatever RomM does not emit itself, and
        entries with no ROM in the database are carried over untouched.
        """
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        roms = db_rom_handler.get_roms_scalar(
            platform_ids=[platform_id], **HAS_FILE_ON_DISK_FILTERS
        )

        existing = existing or ExistingPegasus()
        unmatched_games = dict(enumerate(existing.games))
        game_index_by_file = {
            name: index
            for index, game in enumerate(existing.games)
            for name in game.file_names()
        }

        lines: list[str] = list(existing.preamble)
        collection_name, shortname = self._resolve_collection(platform)
        lines.append(f"collection: {collection_name}")
        lines.append(f"shortname: {shortname}")
        if existing.header is not None:
            lines.extend(existing.header.lines(skip=COLLECTION_HEADER_KEYS))
        lines.append("")

        game_count = 0
        for rom in roms:
            exported_assets: dict[str, str] = {}

            if platform_dir is not None:
                assets = self._collect_assets(rom)

                claimed: dict[Path, Path] = {}
                for asset_key, source_path in assets.items():
                    subdir = PLATFORM_MEDIA_DIRS[PEGASUS_MEDIA_KEYS[asset_key]]
                    dest_name = f"{rom.fs_name_no_ext}{source_path.suffix}"
                    dest_path = platform_dir / subdir / dest_name

                    # Logo and marquee share one folder; keep both files.
                    if claimed.get(dest_path, source_path) != source_path:
                        dest_name = (
                            f"{rom.fs_name_no_ext}-{asset_key}{source_path.suffix}"
                        )
                        dest_path = platform_dir / subdir / dest_name
                    claimed[dest_path] = source_path

                    if self._copy_asset(source_path, dest_path):
                        exported_assets[asset_key] = f"{subdir}/{dest_name}"

            entry = self._create_game_entry(
                rom,
                request=request,
                exported_assets=exported_assets if exported_assets else None,
            )
            entry_lines = entry.splitlines()

            existing_game = unmatched_games.pop(
                game_index_by_file.get(rom.fs_name, -1), None
            )
            if existing_game is not None:
                emitted_keys = parse_pegasus(entry)[-1].keys()
                entry_lines.extend(existing_game.lines(skip=emitted_keys))

            if game_count > 0:
                lines.append("")
            lines.extend(entry_lines)
            game_count += 1

        for block in [*unmatched_games.values(), *existing.tail]:
            lines.append("")
            lines.extend(block.lines())

        log.info(f"Exported {game_count} ROMs for platform {platform.name}")
        return "\n".join(lines) + "\n", game_count

    def export_platform_to_pegasus(
        self, platform_id: int, request: Request | None
    ) -> str:
        """Export a platform's ROMs to metadata.pegasus.txt format (no asset files copied)."""
        content, _ = self._build_pegasus(
            platform_id, request=request, platform_dir=None
        )
        return content

    async def _read_existing_pegasus(self, metadata_path: str) -> ExistingPegasus:
        """Load the metadata file at ``metadata_path``, or an empty one if absent."""
        if not await fs_platform_handler.file_exists(metadata_path):
            return ExistingPegasus()

        content = await fs_platform_handler.read_file(metadata_path)
        return parse_existing_pegasus(content.decode("utf-8-sig"))

    async def export_platform_to_file(
        self,
        platform_id: int,
        request: Request | None,
    ) -> bool:
        """Merge platform ROMs into the metadata.pegasus.txt in the platform's
        directory, copying media into the ES-DE per-type folders when local_export=True.

        Args:
            platform_id: Platform ID to export
            request: FastAPI request object for URL generation

        Returns:
            True if successful, False otherwise
        """
        try:
            platform = db_platform_handler.get_platform(platform_id)
            if not platform:
                log.error(f"Platform with ID {platform_id} not found")
                return False

            platform_fs_structure = fs_platform_handler.get_platform_fs_structure(
                platform.fs_slug
            )
            platform_dir = (
                fs_platform_handler.base_path / platform_fs_structure
                if self.local_export
                else None
            )
            metadata_path = f"{platform_fs_structure}/metadata.pegasus.txt"

            # A file we cannot read is left alone rather than replaced.
            try:
                existing = await self._read_existing_pegasus(metadata_path)
            except UnicodeDecodeError as e:
                log.error(f"Not overwriting unreadable {metadata_path}: {e}")
                return False

            content, game_count = self._build_pegasus(
                platform_id,
                request=request,
                platform_dir=platform_dir,
                existing=existing,
            )
            await fs_platform_handler.write_file(
                content.encode("utf-8"),
                platform_fs_structure,
                "metadata.pegasus.txt",
            )

            log.info(
                f"Exported metadata.pegasus.txt with {game_count} ROMs for platform {platform.name}"
            )
            return True
        except Exception as e:
            log.error(
                f"Failed to export metadata.pegasus.txt for platform {platform_id}: {e}"
            )
            return False
