from pathlib import PureWindowsPath

from defusedxml import ElementTree as ET

from logger.logger import log

from .platforms import get_platform
from .types import LAUNCHBOX_PLATFORMS_DIR
from .utils import file_name_forms


class LocalSource:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, dict[str, str]]] = {}
        self._mtime: dict[str, int] = {}

    async def get_rom(self, fs_name: str, platform_slug: str) -> dict[str, str] | None:
        if not LAUNCHBOX_PLATFORMS_DIR.exists():
            return None

        platform_name = get_platform(platform_slug).get("name")
        xml_path = (
            LAUNCHBOX_PLATFORMS_DIR / f"{platform_name}.xml" if platform_name else None
        )
        if not xml_path or not xml_path.exists():
            return None

        current_mtime = xml_path.stat().st_mtime_ns
        if (
            platform_slug not in self._cache
            or self._mtime.get(platform_slug) != current_mtime
        ):
            try:
                indexed_val: dict[str, dict[str, str]] = {}
                root = ET.parse(str(xml_path.resolve())).getroot()
                if root is not None:
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
                                for stem in file_name_forms(app_base):
                                    indexed_val.setdefault(f"stem:{stem}", entry)

                        title = (entry.get("Title") or "").strip().lower()
                        if title:
                            indexed_val.setdefault(f"title:{title}", entry)
            except (ET.ParseError, FileNotFoundError, PermissionError) as e:
                log.warning(f"Failed to parse local LaunchBox XML {xml_path}: {e}")
                self._cache[platform_slug] = {}
                self._mtime[platform_slug] = current_mtime
                return None

            self._cache[platform_slug] = indexed_val
            self._mtime[platform_slug] = current_mtime

        indexed_val = self._cache[platform_slug]

        if not indexed_val:
            return None

        fs_key = fs_name.strip().lower()
        if not fs_key:
            return None

        stems = file_name_forms(fs_name)
        probes = [
            fs_key,
            *(f"stem:{stem}" for stem in stems),
            *(f"title:{stem}" for stem in stems),
            f"title:{fs_key}",
        ]

        for probe in dict.fromkeys(probes):
            hit = indexed_val.get(probe)
            if hit is not None:
                return hit

        return None
