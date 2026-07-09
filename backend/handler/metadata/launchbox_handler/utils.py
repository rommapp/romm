import re
from datetime import datetime
from pathlib import Path

from handler.filesystem.base_handler import region_name_to_provider_shortcode

from .types import LAUNCHBOX_LOCAL_DIR

# LaunchBox region names that don't map cleanly onto the shared REGIONS table
# (which ROM filename tags use). Keyed lowercase for case-insensitive lookup.
_LAUNCHBOX_REGION_OVERRIDES: dict[str, str] = {
    "north america": "us",
    "united states": "us",
    "united kingdom": "uk",
    "the netherlands": "nl",
}


def launchbox_region_to_shortcode(region_name: str | None) -> str | None:
    """Map a LaunchBox image Region name to a provider shortcode (e.g. "us").

    LaunchBox labels the US region as "North America", so its names can't be
    compared directly against ROM filename regions; normalize both sides to a
    shortcode before matching.
    """
    if not region_name:
        return None
    key = region_name.strip().lower()
    if key in _LAUNCHBOX_REGION_OVERRIDES:
        return _LAUNCHBOX_REGION_OVERRIDES[key]
    return region_name_to_provider_shortcode(region_name)


def sanitize_filename(stem: str) -> str:
    s = (stem or "").strip()
    s = s.replace("\u2019", "'")
    s = re.sub(r"[:']", "_", s)
    s = re.sub(r"[\\/|<>\"?*]", "_", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"_+", "_", s)
    return s.strip(" .")


def file_uri_for_local_path(path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(LAUNCHBOX_LOCAL_DIR.resolve())
    except ValueError:
        return None
    return f"launchbox-file://{relative.as_posix()}"


def coalesce(*values: object | None) -> str | None:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [p.strip() for p in parts if p and p.strip()]


def dedupe_words(values: list[str | None]) -> list[str]:
    seen = {}
    out: list[str] = []

    for v in values:
        if v is None or not v.strip():
            continue

        v = v.strip()
        key = v.lower()
        if key not in seen:
            seen[key] = len(out)
            out.append(v)
        else:
            idx = seen[key]
            if out[idx].islower() and not v.islower():
                out[idx] = v
    return out


def parse_release_date(value: str | None) -> int | None:
    if not value:
        return None

    try:
        iso = value.replace("Z", "+00:00")
        return int(datetime.fromisoformat(iso).timestamp())
    except ValueError:
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except ValueError:
            continue

    return None


def parse_playmode(play_mode: str | None) -> bool:
    if not play_mode:
        return False
    pm = play_mode.lower()
    return bool(re.search(r"\b(cooperative|coop|co-op)\b", pm))


def parse_videourl(url: str | None) -> str:
    if not url:
        return ""

    if "youtube.com/watch?v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1].split("?")[0]

    return ""
