from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import pycountry
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

from config import LIBRARY_BASE_PATH
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.logger import log


REGION_TO_ALPHA2 = {
    "europe": "eu",
    "world": None,
    "unlicensed": None,
}


def fetch_platform(platform_fs_slug: str):
    """Retrieve platform by file-system slug."""
    return db_platform_handler.get_platform_by_fs_slug(platform_fs_slug)


def fetch_roms_for_platform(platform_id: int):
    """Retrieve all ROM objects for a given platform ID."""
    return db_rom_handler.get_roms(platform_id=platform_id)


def resolve_roms_dir(platform_fs_slug: str) -> Path:
    """Construct and validate the on-disk directory for ROMs."""
    rel = fs_rom_handler.build_upload_fs_path(platform_fs_slug)
    roms_dir = Path(LIBRARY_BASE_PATH) / rel
    return roms_dir if roms_dir.exists() else None


def get_normalized_rating(rom) -> str:
    """
    Return a normalized 0..1 rating (two-decimal string).
    Preference: IGDB → Screenscraper.
    """
    # 1) IGDB aggregated or total rating (out of 100)
    igdb = rom.igdb_metadata or {}
    agg = igdb.get("total_rating") or igdb.get("aggregated_rating")
    if agg is not None:
        raw = float(agg) / 100.0
    else:
        # 2) screenscraper score (out of 10)
        ss_meta = getattr(rom, "ss_metadata", {}) or {}
        ss_score = ss_meta.get("ss_score")
        raw = float(ss_score) / 10.0 if ss_score else 0.0

    # clamp to [0,1] and format
    val = max(0.0, min(raw, 1.0))
    return f"{val:.2f}"


def format_company_list(companies) -> str:
    """Format list of company names from metadata."""
    names = []
    for c in companies:
        if isinstance(c, dict):
            name = c.get("company", {}).get("name")
        else:
            name = c
        if name:
            names.append(name)
    return ", ".join(names)


def format_generic_list(items, key: str = None) -> str:
    """Format list of strings or dicts using an optional dict key."""
    values = []
    for it in items:
        val = it.get(key) if isinstance(it, dict) and key else it
        if val:
            values.append(val)
    return ", ".join(values)


def convert_region_name_to_alpha2(region):
    """
    Convert a region name or country name to its ISO 3166-1 alpha-2 code.
    """
    region = region.strip().lower()
    if region in REGION_TO_ALPHA2:
        return REGION_TO_ALPHA2[region]
    try:
        country = pycountry.countries.lookup(region)
        return country.alpha_2.lower()
    except LookupError:
        return region
    

def convert_language_name_to_alpha2(language):
    """
    Convert a language name to its ISO 639-1 code.
    """
    try:
        lang = pycountry.languages.lookup(language)
        return lang.alpha_2.lower()
    except LookupError:
        return language


def build_game_list_element(roms, platform_id: int) -> ET.Element:
    """Create the root <gameList> element and populate it with <game> children."""

    name_counts = Counter(rom.name for rom in roms if rom.name)
    names_duplicates = {name for name, count in name_counts.items() if count > 1}

    root = ET.Element("gameList")
    for rom in sorted(roms, key=lambda r: r.fs_name.lower()):
        game_el = ET.SubElement(root, "game")

        # path
        ET.SubElement(game_el, "path").text = f"./{rom.fs_name}"

        # name and description
        name = rom.name or rom.fs_name_no_ext
        regions = rom.regions or []
        if name in names_duplicates and regions:
            name = f"{name} ({regions[0]})"
        
        ET.SubElement(game_el, "name").text = name
        ET.SubElement(game_el, "desc").text = rom.summary or ""

        # image and thumbnail paths
        image_path = f"/userdata/images/{platform_id}/{rom.id}/cover/big.png"
        thumb_path = f"/userdata/images/{platform_id}/{rom.id}/screenshots/0.jpg"
        ET.SubElement(game_el, "image").text = image_path
        ET.SubElement(game_el, "thumbnail").text = thumb_path

        # release date (YYYYMMDDT000000)
        rd = ET.SubElement(game_el, "releasedate")
        if rom.first_release_date:
            ts = int(rom.first_release_date) / 1000.0
            rd.text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y%m%dT000000")
        else:
            rd.text = ""

        # publisher
        pub = ET.SubElement(game_el, "publisher")
        pub.text = format_company_list(rom.igdb_metadata.get("companies") or [])

        # genre
        genre = ET.SubElement(game_el, "genre")
        genre.text = format_generic_list(rom.igdb_metadata.get("genres") or [], key="name")

        # players, region, lang
        players = ET.SubElement(game_el, "players")
        modes = rom.igdb_metadata.get("game_modes") or []
        players.text = "2+" if "Multiplayer" in modes else "1" if "Single player" in modes else ""

        region = ET.SubElement(game_el, "region")
        region.text = ",".join(
            convert_region_name_to_alpha2(r) for r in regions or [] if r
        )

        lang = ET.SubElement(game_el, "lang")
        lang.text = ",".join(
            convert_language_name_to_alpha2(l) for l in rom.languages or [] if l
        )

        # rating element
        rating_el = ET.SubElement(game_el, "rating")
        rating_el.text = get_normalized_rating(rom)

        md5 = ET.SubElement(game_el, "md5")
        md5.text = rom.md5_hash or ""

        # scrap attribution
        ET.SubElement(game_el, "scrap", {
            "name": "RomM",
            "date": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        })

    return root


def pretty_write(root: ET.Element, out_path: Path):
    """Write prettified XML to disk."""
    rough = ET.tostring(root, 'utf-8')
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty)


def generate_gamelist(platform_fs_slug: str) -> None:
    platform = fetch_platform(platform_fs_slug)
    if not platform:
        return

    roms = fetch_roms_for_platform(platform.id)
    roms_dir = resolve_roms_dir(platform_fs_slug)
    if not roms_dir:
        return

    root = build_game_list_element(roms, platform.id)
    out_file = roms_dir / "gamelist.xml"
    pretty_write(root, out_file)
    log.info(f"Generated gamelist.xml for platform '{platform_fs_slug}' at {out_file}")
