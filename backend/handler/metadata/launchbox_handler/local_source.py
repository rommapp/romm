from pathlib import Path, PureWindowsPath

from defusedxml import ElementTree as ET
from strsimpy.jaro_winkler import JaroWinkler

from logger.logger import log

from .platforms import get_platform
from .types import LAUNCHBOX_PLATFORMS_DIR
from .utils import normalize_launchbox_name

_jarowinkler = JaroWinkler()
# Minimum Jaro-Winkler similarity score to accept a fuzzy match
_FUZZY_MATCH_THRESHOLD = 0.90


class LocalSource:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, dict[str, str]]] = {}
        # Maps platform_slug → list of (normalized_title, entry) for fuzzy search
        self._title_list: dict[str, list[tuple[str, dict[str, str]]]] = {}
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
                title_list: list[tuple[str, dict[str, str]]] = []
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

                        title = (entry.get("Title") or "").strip().lower()
                        if title:
                            indexed_val.setdefault(f"title:{title}", entry)

                            # Also index by normalized title (OS chars stripped,
                            # diacritics removed) for looser matching
                            normalized_title = normalize_launchbox_name(title)
                            if normalized_title and normalized_title != title:
                                indexed_val.setdefault(
                                    f"title_normalized:{normalized_title}", entry
                                )

                            # Only add to the fuzzy list when normalization
                            # produces a usable key; skip titles that reduce to
                            # empty (e.g. titles composed entirely of special chars)
                            fuzzy_key = normalized_title if normalized_title else title
                            title_list.append((fuzzy_key, entry))
            except (ET.ParseError, FileNotFoundError, PermissionError) as e:
                log.warning(f"Failed to parse local LaunchBox XML {xml_path}: {e}")
                self._cache[platform_slug] = {}
                self._title_list[platform_slug] = []
                self._mtime[platform_slug] = current_mtime
                return None

            self._cache[platform_slug] = indexed_val
            self._title_list[platform_slug] = title_list
            self._mtime[platform_slug] = current_mtime

        indexed_val = self._cache[platform_slug]

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

        by_full_title = indexed_val.get(f"title:{fs_key}")
        if by_full_title is not None:
            return by_full_title

        # Try normalized lookups (handles OS-restricted chars and diacritics)
        normalized_stem = normalize_launchbox_name(stem) if stem else ""
        if normalized_stem:
            by_normalized_title = indexed_val.get(
                f"title_normalized:{normalized_stem}"
            )
            if by_normalized_title is not None:
                return by_normalized_title

        normalized_key = normalize_launchbox_name(fs_key)
        if normalized_key and normalized_key != normalized_stem:
            by_normalized_key = indexed_val.get(
                f"title_normalized:{normalized_key}"
            )
            if by_normalized_key is not None:
                return by_normalized_key

        # Last resort: fuzzy match over all titles for this platform
        search_norm = normalized_stem or normalized_key
        if not search_norm:
            return None

        title_list = self._title_list.get(platform_slug, [])
        best_score = 0.0
        best_entry: dict[str, str] | None = None

        for norm_title, entry in title_list:
            score = _jarowinkler.similarity(search_norm, norm_title)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= _FUZZY_MATCH_THRESHOLD and best_entry is not None:
            log.debug(
                f"Fuzzy-matched '{fs_name}' → '{best_entry.get('Title', '')}' "
                f"(score {best_score:.3f})"
            )
            return best_entry

        return None
