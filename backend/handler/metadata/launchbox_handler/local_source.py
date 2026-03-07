import json
from pathlib import Path, PureWindowsPath

from defusedxml import ElementTree as ET

from handler.redis_handler import async_cache
from logger.logger import log

from .platforms import get_platform
from .types import LAUNCHBOX_PLATFORMS_DIR, LAUNCHBOX_XML_INDEX_KEY


class LocalSource:
    async def get_rom(self, fs_name: str, platform_slug: str) -> dict[str, str] | None:
        if not LAUNCHBOX_PLATFORMS_DIR.exists():
            return None

        platform_name = get_platform(platform_slug).get("name")
        xml_path = (
            LAUNCHBOX_PLATFORMS_DIR / f"{platform_name}.xml" if platform_name else None
        )
        if not xml_path or not xml_path.exists():
            return None

        try:
            xml_path_str = str(xml_path.resolve())
            mtime_ns = xml_path.stat().st_mtime_ns
            indexed_val = {}

            cached_str = await async_cache.hget(LAUNCHBOX_XML_INDEX_KEY, xml_path_str)
            if cached_str:
                cached = json.loads(cached_str)
                if cached[0] == mtime_ns:
                    indexed_val = cached[1]
                else:
                    cached = None
            else:
                cached = None

            if cached is None:
                root = ET.parse(xml_path_str).getroot()
                if root:
                    for game_elem in root.findall(".//Game"):
                        entry: dict[str, str] = {}
                        for child_elem in game_elem:
                            if child_elem.tag and child_elem.text is not None:
                                entry[child_elem.tag] = child_elem.text
                        if not entry:
                            continue

                        app_path = (entry.get("ApplicationPath") or "").strip()
                        if app_path:
                            app_base = PureWindowsPath(app_path).name.strip().lower()
                            if app_base:
                                indexed_val.setdefault(app_base, entry)

                        title = (entry.get("Title") or "").strip().lower()
                        if title:
                            indexed_val.setdefault(f"title:{title}", entry)

                    await async_cache.hset(
                        LAUNCHBOX_XML_INDEX_KEY,
                        xml_path_str,
                        json.dumps((mtime_ns, indexed_val)),
                    )
        except (ET.ParseError, FileNotFoundError, PermissionError) as e:
            log.warning(f"Failed to parse local LaunchBox XML {xml_path}: {e}")
            return None

        if not indexed_val:
            return None

        fs_key = fs_name.strip().lower()
        if not fs_key:
            return None

        direct = indexed_val.get(fs_key)
        if direct is not None:
            return direct

        try:
            stem = Path(fs_name).stem.strip().lower()
        except Exception:
            stem = ""

        if stem:
            by_title = indexed_val.get(f"title:{stem}")
            if by_title is not None:
                return by_title

        return indexed_val.get(f"title:{fs_key}")
