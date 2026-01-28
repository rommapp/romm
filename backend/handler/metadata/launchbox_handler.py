import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Final, NotRequired, TypedDict

import pydash
from defusedxml import ElementTree as ET

from config import LAUNCHBOX_API_ENABLED, ROMM_BASE_PATH
from handler.redis_handler import async_cache
from logger.logger import log
from utils.database import safe_int, safe_str_to_bool

from .base_handler import BaseRom, MetadataHandler
from .base_handler import UniversalPlatformSlug as UPS

LAUNCHBOX_PLATFORMS_KEY: Final[str] = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final[str] = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final[str] = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY: Final[str] = (
    "romm:launchbox_metadata_alternate_name"
)
LAUNCHBOX_METADATA_IMAGE_KEY: Final[str] = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final[str] = "romm:launchbox_mame"
LAUNCHBOX_FILES_KEY: Final[str] = "romm:launchbox_files"
LAUNCHBOX_XML_INDEX_KEY: Final[str] = "romm:launchbox_xml_index"


LAUNCHBOX_LOCAL_DIR: Final[Path] = Path(ROMM_BASE_PATH) / "temp"
LAUNCHBOX_PLATFORMS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Data" / "Platforms"
LAUNCHBOX_IMAGES_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Images"
LAUNCHBOX_MANUALS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Manuals"
LAUNCHBOX_VIDEOS_DIR: Final[Path] = LAUNCHBOX_LOCAL_DIR / "Videos"

# Regex to detect LaunchBox ID tags in filenames like (launchbox-12345)
LAUNCHBOX_TAG_REGEX = re.compile(r"\(launchbox-(\d+)\)", re.IGNORECASE)
DASH_COLON_REGEX = re.compile(r"\s?-\s")


class LaunchboxImage(TypedDict):
    url: str
    type: NotRequired[str]
    region: NotRequired[str]


class LaunchboxPlatform(TypedDict):
    slug: str
    launchbox_id: int | None
    name: NotRequired[str]
    images: NotRequired[list[LaunchboxImage]]


class LaunchboxMetadata(TypedDict):
    first_release_date: int | None
    max_players: NotRequired[int]
    release_type: NotRequired[str]
    cooperative: NotRequired[bool]
    youtube_video_id: NotRequired[str]
    community_rating: NotRequired[float]
    community_rating_count: NotRequired[int]
    wikipedia_url: NotRequired[str]
    esrb: NotRequired[str]
    genres: NotRequired[list[str]]
    companies: NotRequired[list[str]]
    images: list[LaunchboxImage]


class LaunchboxRom(BaseRom):
    launchbox_id: int | None
    launchbox_metadata: NotRequired[LaunchboxMetadata]


def _sanitize_filename(stem: str) -> str:
    s = (stem or "").strip()
    s = s.replace("’", "'")
    s = re.sub(r"[:']", "_", s)
    s = re.sub(r"[\\/|<>\"?*]", "_", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"_+", "_", s)
    return s.strip(" .")


def _file_uri_for_local_path(path: Path) -> str | None:
    try:
        _ = path.resolve().relative_to(LAUNCHBOX_LOCAL_DIR.resolve())
    except ValueError:
        return None
    return f"file://{str(path)}"


def _coalesce(*values: object | None) -> str | None:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [p.strip() for p in parts if p and p.strip()]


def _dedupe_words(values):
    seen = {}
    out: list[str] = []

    for v in pydash.compact(pydash.map_(values, str.strip)):
        key = v.lower()
        if key not in seen:
            seen[key] = len(out)
            out.append(v)
        else:
            idx = seen[key]
            if out[idx].islower() and not v.islower():
                out[idx] = v
    return out


def _parse_release_date(value: str | None) -> int | None:
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


def _parse_playmode(play_mode: str | None) -> bool:
    if not play_mode:
        return False
    pm = play_mode.lower()
    return bool(re.search(r"\b(cooperative|coop|co-op)\b", pm))


def _parse_videourl(url: str | None) -> str:
    if not url:
        return ""

    if "youtube.com/watch?v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1].split("?")[0]

    return ""


def build_launchbox_metadata(
    *,
    local: dict[str, str] | None = None,
    remote: dict | None = None,
    images: list[LaunchboxImage],
    **kwargs: object,
) -> LaunchboxMetadata:
    if local is None and isinstance(kwargs.get("local_entry"), dict):
        local = kwargs["local_entry"]  # type: ignore[assignment]

    local_release_date = local.get("ReleaseDate") if local else None
    remote_release_date = remote.get("ReleaseDate") if remote else None
    release_date_raw = _coalesce(local_release_date, remote_release_date)
    first_release_date = _parse_release_date(release_date_raw)

    max_players_raw = _coalesce(
        local.get("MaxPlayers") if local else None,
        remote.get("MaxPlayers") if remote else None,
    )
    try:
        max_players = int(max_players_raw or 0)
    except (TypeError, ValueError):
        max_players = 0

    release_type = (
        _coalesce(
            local.get("ReleaseType") if local else None,
            remote.get("ReleaseType") if remote else None,
        )
        or ""
    )

    if local and _coalesce(local.get("PlayMode")):
        cooperative = _parse_playmode(local.get("PlayMode"))
    else:
        cooperative = safe_str_to_bool(
            (remote.get("Cooperative") if remote else None) or "false"
        )

    video_url = _coalesce(
        (local.get("VideoUrl") if local else None),
        (remote.get("VideoURL") if remote else None),
    )

    community_rating_raw = _coalesce(
        local.get("CommunityStarRating") if local else None,
        remote.get("CommunityRating") if remote else None,
    )
    try:
        community_rating = float(community_rating_raw or 0.0)
    except (TypeError, ValueError):
        community_rating = 0.0

    community_rating_count_raw = _coalesce(
        local.get("CommunityStarRatingTotalVotes") if local else None,
        remote.get("CommunityRatingCount") if remote else None,
    )
    try:
        community_rating_count = int(community_rating_count_raw or 0)
    except (TypeError, ValueError):
        community_rating_count = 0

    wikipedia_url = (
        _coalesce(
            local.get("WikipediaURL") if local else None,
            remote.get("WikipediaURL") if remote else None,
        )
        or ""
    )

    esrb_raw = _coalesce(
        (local.get("Rating") if local else None),
        (remote.get("ESRB") if remote else None),
    )
    esrb = (esrb_raw or "").split(" - ")[0].strip()

    genres_raw = _coalesce(
        local.get("Genre") if local else None,
        remote.get("Genres") if remote else None,
    )
    genres = _parse_list(genres_raw)

    publisher = _coalesce(
        local.get("Publisher") if local else None,
        remote.get("Publisher") if remote else None,
    )
    developer = _coalesce(
        local.get("Developer") if local else None,
        remote.get("Developer") if remote else None,
    )
    companies = _dedupe_words([publisher, developer])

    return LaunchboxMetadata(
        {
            "first_release_date": first_release_date,
            "max_players": max_players,
            "release_type": release_type,
            "cooperative": cooperative,
            "youtube_video_id": _parse_videourl(video_url),
            "community_rating": community_rating,
            "community_rating_count": community_rating_count,
            "wikipedia_url": wikipedia_url,
            "esrb": esrb,
            "genres": genres,
            "companies": companies,
            "images": images,
        }
    )


class _LocalMediaContext(TypedDict):
    base: Path
    stems: list[str]
    preferred_regions: list[str]


@dataclass(frozen=True, slots=True)
class _MediaRequest:
    platform_name: str | None
    fs_name: str
    title: str
    region_hint: str | None
    remote_images: list[dict] | None
    remote_enabled: bool


def _local_media_req(
    *,
    platform_name: str | None,
    fs_name: str,
    local: dict[str, str] | None,
    remote: dict | None,
    remote_images: list[dict] | None,
    remote_enabled: bool,
) -> _MediaRequest:
    title = ((local or {}).get("Title") or "").strip()
    region_hint = ((local or {}).get("Region") or "").strip() or None
    return _MediaRequest(
        platform_name,
        fs_name,
        title,
        region_hint,
        remote_images,
        remote_enabled,
    )


def _remote_media_req(
    *,
    remote: dict | None,
    remote_images: list[dict] | None,
    remote_enabled: bool,
) -> _MediaRequest:
    title = ((remote or {}).get("Name") or "").strip()
    return _MediaRequest(
        None,
        "",
        title,
        None,
        remote_images,
        remote_enabled,
    )


def _build_local_media_context(
    req: _MediaRequest,
    base_dir: Path,
    *,
    include_region_hints: bool = True,
) -> _LocalMediaContext | None:
    if not req.platform_name:
        return None

    if not base_dir.exists():
        return None
    base = (base_dir / req.platform_name).resolve()
    if not base.is_dir():
        return None

    stems: list[str] = []
    if req.fs_name:
        stems.append(Path(req.fs_name).stem)
    if req.title:
        stems.append(req.title)

    out: list[str] = []
    for s in stems:
        clean = _sanitize_filename(s)
        if clean and clean not in out:
            out.append(clean)
    stems = out
    if not stems:
        return None

    preferred_regions: list[str] = []
    if include_region_hints and req.region_hint:
        region_hint = req.region_hint.strip()
        if region_hint:
            preferred_regions.append(region_hint)
            if "," in region_hint:
                preferred_regions.extend(
                    [r.strip() for r in region_hint.split(",") if r.strip()]
                )

    return {
        "base": base,
        "stems": stems,
        "preferred_regions": preferred_regions,
    }


def _find_local_media_candidates(
    ctx: _LocalMediaContext,
    category_name: str,
    *,
    exts: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp"),
    indexed_preference: tuple[int, ...] | None = None,
    indexed_only_preferred: bool = False,
) -> tuple[list[Path], str]:
    category_dir = ctx["base"] / category_name
    if not category_dir.is_dir():
        return [], ""

    search_dirs: list[Path] = []

    for region in ctx["preferred_regions"]:
        p = category_dir / region
        if p.exists() and p.is_dir() and p not in search_dirs:
            search_dirs.append(p)

    for p in sorted(
        [p for p in category_dir.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    ):
        if p not in search_dirs:
            search_dirs.append(p)

    if category_dir not in search_dirs:
        search_dirs.append(category_dir)

    if not search_dirs:
        return [], ""
    allowed_exts = {e.lower() for e in exts}

    def _candidates(d: Path, stem: str) -> list[Path]:
        if not stem:
            return []

        plain: Path | None = None
        indexed: list[tuple[int, Path]] = []
        prefix = f"{stem}-"

        for p in d.iterdir():
            if not (p.is_file() and p.suffix.lower() in allowed_exts):
                continue

            stem_name = p.stem
            if stem_name == stem:
                plain = p
                continue

            if stem_name.startswith(prefix):
                suffix = stem_name[len(prefix) :]
                if suffix.isdigit():
                    indexed.append((int(suffix), p))

        if indexed:
            indexed.sort(key=lambda t: (t[0], t[1].name.lower()))
            if indexed_preference:
                indexed_by_num: dict[int, Path] = {n: p for n, p in indexed}
                preferred_hits = [
                    indexed_by_num[n] for n in indexed_preference if n in indexed_by_num
                ]
                if preferred_hits:
                    return preferred_hits
                if indexed_only_preferred:
                    return [plain] if plain else []

            return [p for _, p in indexed]

        return [plain] if plain else []

    for d in search_dirs:
        region = "" if d == category_dir else d.name
        for stem in ctx["stems"]:
            candidate_files = _candidates(d, stem)
            if candidate_files:
                return candidate_files, region

    return [], ""


def _get_cover(req: _MediaRequest) -> str | None:
    cover: str | None = None

    cover_priority_types = (
        "Box - Front",
        "Box - Front - Reconstructed",
        "Fanart - Box - Front",
        "Box - 3D",
        "Amazon Poster",
        "Epic Games Poster",
        "GOG Poster",
        "Steam Poster",
    )

    # Remote media fallback (only if allowed)
    if req.remote_enabled and req.remote_images:
        best_cover: dict | None = None
        for image_type in cover_priority_types:
            for image in req.remote_images:
                if image.get("Type") == image_type and image.get("FileName"):
                    best_cover = image
                    break
            if best_cover is not None:
                break

        if best_cover and best_cover.get("FileName"):
            cover = f"https://images.launchbox-app.com/{best_cover.get('FileName')}"

    ctx = _build_local_media_context(
        req, LAUNCHBOX_IMAGES_DIR, include_region_hints=True
    )
    if ctx is not None:
        for category in cover_priority_types:
            candidate_files, _region = _find_local_media_candidates(
                ctx,
                category,
                indexed_preference=(1,),
                indexed_only_preferred=True,
            )
            if not candidate_files:
                continue

            cover_path = candidate_files[0]
            url = _file_uri_for_local_path(cover_path)
            if url:
                cover = url
                break

    return cover


def _get_screenshots(req: _MediaRequest) -> list[str]:
    screenshots: list[str] = []

    # Remote media fallback (only if allowed)
    if req.remote_enabled and req.remote_images:
        screenshots = [
            f"https://images.launchbox-app.com/{image.get('FileName')}"
            for image in req.remote_images
            if image.get("FileName") and "Screenshot" in image.get("Type", "")
        ]

    ctx = _build_local_media_context(
        req, LAUNCHBOX_IMAGES_DIR, include_region_hints=True
    )
    if ctx is not None:
        local_screens: list[str] = []
        seen: set[str] = set()
        for dir_name in (
            "Amazon Screenshot",
            "Epic Games Screenshot",
            "GOG Screenshot",
            "Origin Screenshot",
            "Screenshot - Game Title",
            "Screenshot - Game Select",
            "Screenshot - Gameplay",
            "Screenshot - High Scores",
            "Screenshot - Game Over",
            "Steam Screenshot",
        ):
            candidate_files, _region = _find_local_media_candidates(ctx, dir_name)
            for p in candidate_files:
                url = _file_uri_for_local_path(p)
                if url and url not in seen:
                    seen.add(url)
                    local_screens.append(url)

        if local_screens:
            screenshots = local_screens

    return screenshots


def _get_manuals(req: _MediaRequest) -> str | None:
    manual: str | None = None

    ctx = _build_local_media_context(
        req, LAUNCHBOX_MANUALS_DIR, include_region_hints=False
    )
    if ctx is None:
        return manual

    pdfs: list[Path] = [
        p for p in ctx["base"].iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    ]
    if not pdfs:
        return manual

    def _key(p: Path) -> str:
        return _sanitize_filename(p.stem).lower()

    pdfs_sorted = sorted(pdfs, key=lambda p: (len(p.name), p.name.lower()))

    stems_lower = [s.lower() for s in ctx["stems"]]

    for stem in stems_lower:
        for p in pdfs_sorted:
            if _key(p) == stem:
                url = _file_uri_for_local_path(p)
                if url:
                    return url

    for stem in stems_lower:
        for p in pdfs_sorted:
            if _key(p).startswith(stem):
                url = _file_uri_for_local_path(p)
                if url:
                    return url

    return manual


def _get_images(req: _MediaRequest) -> list[LaunchboxImage]:
    images: list[LaunchboxImage] = []

    # Remote media fallback (only if allowed)
    if req.remote_enabled and req.remote_images:
        images = [
            LaunchboxImage(
                {
                    "url": f"https://images.launchbox-app.com/{image['FileName']}",
                    "type": image.get("Type", ""),
                    "region": image.get("Region", ""),
                }
            )
            for image in req.remote_images
            if image.get("FileName")
        ]

    ctx = _build_local_media_context(
        req, LAUNCHBOX_IMAGES_DIR, include_region_hints=True
    )
    if ctx is not None:
        local_images: list[LaunchboxImage] = []
        for dir_name in (
            "Advertisement Flyer - Back",
            "Advertisement Flyer - Front",
            "Box - Back",
            "Box - Back - Reconstructed",
            "Box - Full",
            "Box - Spine",
            "Cart - Front",
            "Cart - 3D",
            "Clear Logo",
            "Fanart - Box - Back",
            "Fanart - Background",  # Later separate in new category for rom header
            "Amazon Background",  # Later separate in new category for rom header
            "Epic Games Background",  # Later separate in new category for rom header
            "Origin Background",  # Later separate in new category for rom header
            "Uplay Background",  # Later separate in new category for rom header
        ):
            candidate_files, region = _find_local_media_candidates(ctx, dir_name)
            for p in candidate_files:
                url = _file_uri_for_local_path(p)
                if not url:
                    continue
                local_images.append(
                    LaunchboxImage(
                        {
                            "url": url,
                            "type": dir_name,
                            "region": region,
                        }
                    )
                )

        if local_images:
            images = local_images

    seen_images: dict[str, LaunchboxImage] = {}
    for img in images:
        if img["url"] not in seen_images:
            seen_images[img["url"]] = img

    return list(seen_images.values())


def build_rom(
    *,
    local: dict[str, str] | None,
    remote: dict | None,
    launchbox_id: int | None,
    media_req: _MediaRequest | None = None,
) -> LaunchboxRom:
    images: list[LaunchboxImage] = (
        _get_images(media_req) if media_req is not None else []
    )

    url_cover: str | None = None
    url_screenshots: list[str] = []
    url_manual: str | None = None
    if media_req is not None:
        url_cover = _get_cover(media_req)
        url_screenshots = _get_screenshots(media_req)
        url_manual = _get_manuals(media_req)
    url_screenshots = url_screenshots or []

    name = (
        _coalesce(
            (local.get("Title") if local else None),
            (remote.get("Name") if remote else None),
        )
        or ""
    ).strip()

    summary = (
        _coalesce(
            (local.get("Notes") if local else None),
            (remote.get("Overview") if remote else None),
        )
        or ""
    ).strip()

    return LaunchboxRom(
        launchbox_id=launchbox_id,
        name=name,
        summary=summary,
        url_cover=url_cover or "",
        url_screenshots=url_screenshots,
        url_manual=url_manual or "",
        launchbox_metadata=build_launchbox_metadata(
            local=local,
            remote=remote,
            images=images,
        ),
    )


class LaunchboxHandler(MetadataHandler):
    @classmethod
    def is_enabled(cls) -> bool:
        return LAUNCHBOX_API_ENABLED or LAUNCHBOX_PLATFORMS_DIR.exists()

    async def heartbeat(self) -> bool:
        return self.is_enabled()

    async def _fetch_remote_images(
        self,
        *,
        remote: dict | None = None,
        database_id: str | int | None = None,
        remote_enabled: bool = True,
    ) -> list[dict] | None:
        if not remote_enabled:
            return None

        resolved_id = database_id
        if resolved_id is None and remote is not None:
            resolved_id = remote.get("DatabaseID")

        if not resolved_id:
            return None

        metadata_image_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_IMAGE_KEY, str(resolved_id)
        )

        if not metadata_image_index_entry:
            return None

        return json.loads(metadata_image_index_entry)

    def get_platform(self, slug: str) -> LaunchboxPlatform:
        slug_clean = slug.strip().lower()
        resolved: UPS | None = None
        for candidate in (
            slug_clean,
            slug_clean.replace("-", ""),
            slug_clean.replace("_", ""),
            slug_clean.replace("-", "").replace("_", ""),
        ):
            if not candidate:
                continue
            try:
                ups = UPS(candidate)
            except ValueError:
                continue
            if ups in LAUNCHBOX_PLATFORM_LIST:
                resolved = ups
                break

        if resolved is None:
            return LaunchboxPlatform(slug=slug_clean, launchbox_id=None)

        platform = LAUNCHBOX_PLATFORM_LIST[resolved]

        return LaunchboxPlatform(
            slug=slug_clean,
            launchbox_id=platform["id"],
            name=platform["name"],
        )

    async def _get_local_rom(
        self, fs_name: str, platform_slug: str
    ) -> dict[str, str] | None:
        if not LAUNCHBOX_PLATFORMS_DIR.exists():
            return None

        platform_name = self.get_platform(platform_slug).get("name")
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

    async def _get_remote_rom(
        self,
        file_name: str,
        platform_slug: str,
        *,
        assume_cache_present: bool = False,
    ) -> dict | None:
        if not assume_cache_present and not (
            await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)
        ):
            log.error("Could not find the Launchbox Metadata.xml file in cache")
            return None

        lb_platform = self.get_platform(platform_slug)
        platform_name = lb_platform.get("name", None)
        if not platform_name:
            return None

        file_name_clean = (file_name or "").strip()
        if not file_name_clean:
            return None

        candidates: list[str] = [file_name_clean]
        lower = file_name_clean.lower()
        if lower != file_name_clean:
            candidates.append(lower)

        for candidate in candidates:
            metadata_name_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_NAME_KEY, f"{candidate}:{platform_name}"
            )
            if metadata_name_index_entry:
                return json.loads(metadata_name_index_entry)

        for candidate in candidates:
            metadata_alternate_name_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY, candidate
            )
            if not metadata_alternate_name_index_entry:
                continue

            metadata_alternate_name_index_entry = json.loads(
                metadata_alternate_name_index_entry
            )
            database_id = metadata_alternate_name_index_entry["DatabaseID"]
            metadata_database_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_DATABASE_ID_KEY, database_id
            )
            if metadata_database_index_entry:
                return json.loads(metadata_database_index_entry)

        return None

    async def get_rom(
        self,
        fs_name: str,
        platform_slug: str,
        keep_tags: bool = False,
        *,
        remote_enabled: bool = True,
    ) -> LaunchboxRom:
        from handler.filesystem import fs_rom_handler

        fallback_rom = LaunchboxRom(launchbox_id=None)

        if not self.is_enabled():
            return fallback_rom

        local = await self._get_local_rom(fs_name, platform_slug)

        remote_available = remote_enabled and bool(
            await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)
        )

        if local is not None:
            launchbox_id_local = safe_int(local.get("DatabaseID"))
            remote: dict | None = None
            if remote_available:
                if launchbox_id_local:
                    metadata_database_index_entry = await async_cache.hget(
                        LAUNCHBOX_METADATA_DATABASE_ID_KEY, str(launchbox_id_local)
                    )
                    if metadata_database_index_entry:
                        remote = json.loads(metadata_database_index_entry)

                if remote is None:
                    local_title = (local.get("Title") or "").strip()
                    if local_title:
                        remote = await self._get_remote_rom(
                            local_title,
                            platform_slug,
                            assume_cache_present=True,
                        )
            platform_name = self.get_platform(platform_slug).get("name")
            remote_images = await self._fetch_remote_images(
                remote=remote, remote_enabled=remote_available
            )
            media_req = _local_media_req(
                platform_name=platform_name,
                fs_name=fs_name,
                local=local,
                remote=remote,
                remote_images=remote_images,
                remote_enabled=remote_available,
            )
            return build_rom(
                local=local,
                remote=remote,
                launchbox_id=launchbox_id_local
                or (remote.get("DatabaseID") if remote else None),
                media_req=media_req,
            )

        if not remote_available:
            return fallback_rom

        match = LAUNCHBOX_TAG_REGEX.search(fs_name)
        launchbox_id_from_tag = int(match.group(1)) if match else None

        if launchbox_id_from_tag is not None:
            log.debug(f"Found LaunchBox ID tag in filename: {launchbox_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(
                launchbox_id_from_tag, remote_enabled=remote_enabled
            )
            if rom_by_id["launchbox_id"]:
                log.debug(
                    f"Successfully matched ROM by LaunchBox ID tag: {fs_name} -> {launchbox_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"LaunchBox ID {launchbox_id_from_tag} from filename tag not found in LaunchBox"
                )

        # `keep_tags` prevents stripping content that is considered a tag, e.g., anything between `()` or `[]`.
        # By default, tags are still stripped to keep scan behavior consistent with previous versions.
        # If `keep_tags` is True, the full `fs_name` is used for searching.
        if not keep_tags:
            search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
            # We replace " - "/"- " with ": " to match Launchbox's naming convention
            search_term = re.sub(DASH_COLON_REGEX, ": ", search_term)
        else:
            search_term = fs_name

        search_term = search_term.lower()

        index_entry = await self._get_remote_rom(
            search_term,
            platform_slug,
            assume_cache_present=True,
        )

        if not index_entry:
            return fallback_rom

        remote_images = await self._fetch_remote_images(
            remote=index_entry, remote_enabled=remote_available
        )
        media_req = _remote_media_req(
            remote=index_entry,
            remote_images=remote_images,
            remote_enabled=remote_available,
        )

        return build_rom(
            local=None,
            remote=index_entry,
            launchbox_id=index_entry["DatabaseID"],
            media_req=media_req,
        )

    async def get_rom_by_id(
        self, database_id: int, *, remote_enabled: bool = True
    ) -> LaunchboxRom:
        if not self.is_enabled():
            return LaunchboxRom(launchbox_id=None)

        if not remote_enabled:
            return LaunchboxRom(launchbox_id=None)

        metadata_database_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_DATABASE_ID_KEY, str(database_id)
        )

        if not metadata_database_index_entry:
            return LaunchboxRom(launchbox_id=None)

        metadata_database_index_entry = json.loads(metadata_database_index_entry)
        remote_images = await self._fetch_remote_images(
            remote=metadata_database_index_entry, remote_enabled=remote_enabled
        )
        media_req = _remote_media_req(
            remote=metadata_database_index_entry,
            remote_images=remote_images,
            remote_enabled=remote_enabled,
        )

        return build_rom(
            local=None,
            remote=metadata_database_index_entry,
            launchbox_id=database_id,
            media_req=media_req,
        )

    async def get_matched_roms_by_name(
        self, search_term: str, platform_slug: str
    ) -> list[LaunchboxRom]:
        if not self.is_enabled():
            return []

        rom = await self.get_rom(search_term, platform_slug, True)
        return [rom] if rom else []

    async def get_matched_rom_by_id(self, database_id: int) -> LaunchboxRom | None:
        if not self.is_enabled():
            return None

        rom = await self.get_rom_by_id(database_id, remote_enabled=True)
        return rom if rom.get("launchbox_id") else None


class SlugToLaunchboxId(TypedDict):
    id: int
    name: str


LAUNCHBOX_PLATFORM_LIST: dict[UPS, SlugToLaunchboxId] = {
    UPS.VECTOR_06C: {"id": 199, "name": "Vector-06C"},
    UPS._3DO: {"id": 1, "name": "3DO Interactive Multiplayer"},
    UPS.N3DS: {"id": 24, "name": "Nintendo 3DS"},
    UPS.N64DD: {"id": 194, "name": "Nintendo 64DD"},
    UPS.ACORN_ARCHIMEDES: {"id": 74, "name": "Acorn Archimedes"},
    UPS.ACORN_ELECTRON: {"id": 65, "name": "Acorn Electron"},
    UPS.ACPC: {"id": 3, "name": "Amstrad CPC"},
    UPS.ACTION_MAX: {"id": 154, "name": "WoW Action Max"},
    UPS.ADVENTURE_VISION: {
        "id": 67,
        "name": "Entex Adventure Vision",
    },
    UPS.ALICE_3290: {"id": 189, "name": "Matra and Hachette Alice"},
    UPS.AMIGA: {"id": 2, "name": "Commodore Amiga"},
    UPS.AMIGA_CD32: {"id": 119, "name": "Commodore Amiga CD32"},
    UPS.AMSTRAD_GX4000: {"id": 109, "name": "Amstrad GX4000"},
    UPS.ANDROID: {"id": 4, "name": "Android"},
    UPS.APF: {"id": 68, "name": "APF Imagination Machine"},
    UPS.APPLE_IIGS: {"id": 112, "name": "Apple IIGS"},
    UPS.APPLEII: {"id": 110, "name": "Apple II"},
    UPS.ARCADE: {"id": 5, "name": "Arcade"},
    UPS.ARCADIA_2001: {"id": 79, "name": "Emerson Arcadia 2001"},
    UPS.ASTROCADE: {"id": 77, "name": "Bally Astrocade"},
    UPS.ATARI_JAGUAR_CD: {"id": 10, "name": "Atari Jaguar CD"},
    UPS.ATARI_ST: {"id": 76, "name": "Atari ST"},
    UPS.ATARI_XEGS: {"id": 12, "name": "Atari XEGS"},
    UPS.ATARI2600: {"id": 6, "name": "Atari 2600"},
    UPS.ATARI5200: {"id": 7, "name": "Atari 5200"},
    UPS.ATARI7800: {"id": 8, "name": "Atari 7800"},
    UPS.ATARI800: {"id": 102, "name": "Atari 800"},
    UPS.ATMOS: {"id": 64, "name": "Oric Atmos"},
    UPS.ATOM: {"id": 107, "name": "Acorn Atom"},
    UPS.BBCMICRO: {"id": 59, "name": "BBC Microcomputer System"},
    UPS.BK: {"id": 131, "name": "Elektronika BK"},
    UPS.BK_01: {"id": 175, "name": "Apogee BK-01"},
    UPS.BROWSER: {"id": 85, "name": "Web Browser"},
    UPS.C_PLUS_4: {"id": 121, "name": "Commodore Plus 4"},
    UPS.C128: {"id": 118, "name": "Commodore 128"},
    UPS.C64: {"id": 14, "name": "Commodore 64"},
    UPS.CAMPUTERS_LYNX: {"id": 61, "name": "Camputers Lynx"},
    UPS.CASIO_LOOPY: {"id": 114, "name": "Casio Loopy"},
    UPS.CASIO_PV_1000: {"id": 115, "name": "Casio PV-1000"},
    UPS.COLECOADAM: {"id": 117, "name": "Coleco Adam"},
    UPS.COLECOVISION: {"id": 13, "name": "ColecoVision"},
    UPS.COLOUR_GENIE: {"id": 73, "name": "EACA EG2000 Colour Genie"},
    UPS.COMMODORE_CDTV: {"id": 120, "name": "Commodore CDTV"},
    UPS.CPET: {"id": 180, "name": "Commodore PET"},
    UPS.CREATIVISION: {"id": 152, "name": "VTech CreatiVision"},
    UPS.DC: {"id": 40, "name": "Sega Dreamcast"},
    UPS.DOS: {"id": 83, "name": "MS-DOS"},
    UPS.DRAGON_32_SLASH_64: {"id": 66, "name": "Dragon 32/64"},
    UPS.ENTERPRISE: {"id": 72, "name": "Enterprise"},
    UPS.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 132,
        "name": "Epoch Game Pocket Computer",
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 81,
        "name": "Epoch Super Cassette Vision",
    },
    UPS.EXELVISION: {"id": 183, "name": "Exelvision EXL 100"},
    UPS.EXIDY_SORCERER: {"id": 184, "name": "Exidy Sorcerer"},
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 58,
        "name": "Fairchild Channel F",
    },
    UPS.FAMICOM: {"id": 157, "name": "Nintendo Famicom Disk System"},
    UPS.FDS: {"id": 157, "name": "Nintendo Famicom Disk System"},
    UPS.FM_7: {"id": 186, "name": "Fujitsu FM-7"},
    UPS.FM_TOWNS: {"id": 124, "name": "Fujitsu FM Towns Marty"},
    UPS.G_AND_W: {"id": 166, "name": "Nintendo Game & Watch"},
    UPS.GAME_DOT_COM: {"id": 63, "name": "Tiger Game.com"},
    UPS.GAME_WAVE: {"id": 216, "name": "GameWave"},
    UPS.GAMEGEAR: {"id": 41, "name": "Sega Game Gear"},
    UPS.GB: {"id": 28, "name": "Nintendo Game Boy"},
    UPS.GBA: {"id": 29, "name": "Nintendo Game Boy Advance"},
    UPS.GBC: {"id": 30, "name": "Nintendo Game Boy Color"},
    UPS.GENESIS: {"id": 42, "name": "Sega Genesis"},
    UPS.GP32: {"id": 135, "name": "GamePark GP32"},
    UPS.HARTUNG: {"id": 136, "name": "Hartung Game Master"},
    UPS.HIKARU: {"id": 208, "name": "Sega Hikaru"},
    UPS.HRX: {"id": 187, "name": "Hector HRX"},
    UPS.HYPERSCAN: {"id": 171, "name": "Mattel HyperScan"},
    UPS.INTELLIVISION: {"id": 15, "name": "Mattel Intellivision"},
    UPS.IOS: {"id": 18, "name": "Apple iOS"},
    UPS.JAGUAR: {"id": 9, "name": "Atari Jaguar"},
    UPS.JUPITER_ACE: {"id": 70, "name": "Jupiter Ace"},
    UPS.LINUX: {"id": 218, "name": "Linux"},
    UPS.LYNX: {"id": 11, "name": "Atari Lynx"},
    UPS.MAC: {"id": 16, "name": "Apple Mac OS"},
    UPS.AQUARIUS: {"id": 69, "name": "Mattel Aquarius"},
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: {"id": 127, "name": "Mega Duck"},
    UPS.MODEL1: {"id": 104, "name": "Sega Model 1"},
    UPS.MODEL2: {"id": 88, "name": "Sega Model 2"},
    UPS.MODEL3: {"id": 94, "name": "Sega Model 3"},
    UPS.MSX: {"id": 82, "name": "Microsoft MSX"},
    UPS.MSX2: {"id": 190, "name": "Microsoft MSX2"},
    UPS.MSX2PLUS: {"id": 191, "name": "Microsoft MSX2+"},
    UPS.MTX512: {"id": 60, "name": "Memotech MTX512"},
    UPS.MUGEN: {"id": 138, "name": "MUGEN"},
    UPS.MULTIVISION: {"id": 197, "name": "Othello Multivision"},
    UPS.N64: {"id": 25, "name": "Nintendo 64"},
    UPS.NDS: {"id": 26, "name": "Nintendo DS"},
    UPS.NEO_GEO_CD: {"id": 167, "name": "SNK Neo Geo CD"},
    UPS.NEO_GEO_POCKET: {"id": 21, "name": "SNK Neo Geo Pocket"},
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 22,
        "name": "SNK Neo Geo Pocket Color",
    },
    UPS.NEOGEOAES: {"id": 23, "name": "SNK Neo Geo AES"},
    UPS.NEOGEOMVS: {"id": 210, "name": "SNK Neo Geo MVS"},
    UPS.NES: {"id": 27, "name": "Nintendo Entertainment System"},
    UPS.NGAGE: {"id": 213, "name": "Nokia N-Gage"},
    UPS.NGC: {"id": 31, "name": "Nintendo GameCube"},
    UPS.NUON: {"id": 126, "name": "Nuon"},
    UPS.ODYSSEY: {"id": 78, "name": "Magnavox Odyssey"},
    UPS.ODYSSEY_2: {
        "id": 57,
        "name": "Magnavox Odyssey 2",
    },
    UPS.OPENBOR: {"id": 139, "name": "OpenBOR"},
    UPS.OUYA: {"id": 35, "name": "Ouya"},
    UPS.PC_8800_SERIES: {"id": 192, "name": "NEC PC-8801"},
    UPS.PC_9800_SERIES: {"id": 193, "name": "NEC PC-9801"},
    UPS.PC_FX: {"id": 161, "name": "NEC PC-FX"},
    UPS.PEGASUS: {"id": 174, "name": "Aamber Pegasus"},
    UPS.PHILIPS_CD_I: {"id": 37, "name": "Philips CD-i"},
    UPS.PHILIPS_VG_5000: {"id": 140, "name": "Philips VG 5000"},
    UPS.PICO: {"id": 220, "name": "PICO-8"},
    UPS.PINBALL: {"id": 151, "name": "Pinball"},
    UPS.POCKETSTATION: {"id": 203, "name": "Sony PocketStation"},
    UPS.POKEMON_MINI: {"id": 195, "name": "Nintendo Pokemon Mini"},
    UPS.PS2: {"id": 48, "name": "Sony Playstation 2"},
    UPS.PS3: {"id": 49, "name": "Sony Playstation 3"},
    UPS.PS4: {"id": 50, "name": "Sony Playstation 4"},
    UPS.PS5: {"id": 219, "name": "Sony Playstation 5"},
    UPS.PSP: {"id": 52, "name": "Sony PSP"},
    UPS.PSP_MINIS: {"id": 202, "name": "Sony PSP Minis"},
    UPS.PSVITA: {"id": 51, "name": "Sony Playstation Vita"},
    UPS.PSX: {"id": 47, "name": "Sony Playstation"},
    UPS.RCA_STUDIO_II: {"id": 142, "name": "RCA Studio II"},
    UPS.SAM_COUPE: {"id": 71, "name": "SAM Coupé"},
    UPS.SATELLAVIEW: {"id": 168, "name": "Nintendo Satellaview"},
    UPS.SATURN: {"id": 45, "name": "Sega Saturn"},
    UPS.SC3000: {"id": 145, "name": "Sega SC-3000"},
    UPS.SCUMMVM: {"id": 143, "name": "ScummVM"},
    UPS.SEGA_PICO: {"id": 105, "name": "Sega Pico"},
    UPS.SEGA32: {"id": 38, "name": "Sega 32X"},
    UPS.SEGACD: {"id": 39, "name": "Sega CD"},
    UPS.SEGACD32: {"id": 173, "name": "Sega CD 32X"},
    UPS.SERIES_X_S: {"id": 222, "name": "Microsoft Xbox Series X/S"},
    UPS.SFAM: {"id": 53, "name": "Super Famicom"},
    UPS.SG1000: {"id": 80, "name": "Sega SG-1000"},
    UPS.SHARP_MZ_80B20002500: {"id": 205, "name": "Sharp MZ-2500"},
    UPS.SHARP_X68000: {"id": 128, "name": "Sharp X68000"},
    UPS.SMS: {"id": 43, "name": "Sega Master System"},
    UPS.SNES: {
        "id": 53,
        "name": "Super Nintendo Entertainment System",
    },
    UPS.SOCRATES: {"id": 198, "name": "VTech Socrates"},
    UPS.SORD_M5: {"id": 148, "name": "Sord M5"},
    UPS.SPECTRAVIDEO: {"id": 201, "name": "Spectravideo"},
    UPS.STV: {"id": 146, "name": "Sega ST-V"},
    UPS.SUPER_VISION_8000: {
        "id": 223,
        "name": "Bandai Super Vision 8000",
    },
    UPS.SUPERGRAFX: {"id": 162, "name": "PC Engine SuperGrafx"},
    UPS.SWITCH: {"id": 211, "name": "Nintendo Switch"},
    UPS.SWITCH_2: {"id": 224, "name": "Nintendo Switch 2"},
    UPS.SYSTEM_32: {"id": 93, "name": "Namco System 22"},
    UPS.SYSTEM16: {"id": 97, "name": "Sega System 16"},
    UPS.SYSTEM32: {"id": 96, "name": "Sega System 32"},
    UPS.TG16: {"id": 54, "name": "NEC TurboGrafx-16"},
    UPS.TI_994A: {"id": 149, "name": "Texas Instruments TI 99/4A"},
    UPS.TOMY_TUTOR: {"id": 200, "name": "Tomy Tutor"},
    UPS.TRS_80: {"id": 129, "name": "Tandy TRS-80"},
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 164,
        "name": "TRS-80 Color Computer",
    },
    UPS.TURBOGRAFX_CD: {"id": 163, "name": "NEC TurboGrafx-CD"},
    UPS.TYPE_X: {"id": 169, "name": "Taito Type X"},
    UPS.VC_4000: {"id": 137, "name": "Interton VC 4000"},
    UPS.VECTREX: {"id": 125, "name": "GCE Vectrex"},
    UPS.VIC_20: {"id": 122, "name": "Commodore VIC-20"},
    UPS.VIDEOPAC_G7400: {"id": 141, "name": "Philips Videopac+"},
    UPS.VIRTUALBOY: {"id": 32, "name": "Nintendo Virtual Boy"},
    UPS.VMU: {"id": 144, "name": "Sega Dreamcast VMU"},
    UPS.VSMILE: {"id": 221, "name": "VTech V.Smile"},
    UPS.SUPERVISION: {"id": 153, "name": "Watara Supervision"},
    UPS.WII: {"id": 33, "name": "Nintendo Wii"},
    UPS.WIIU: {"id": 34, "name": "Nintendo Wii U"},
    UPS.WIN: {"id": 84, "name": "Windows"},
    UPS.WIN3X: {"id": 212, "name": "Windows 3.X"},
    UPS.WONDERSWAN: {"id": 55, "name": "WonderSwan"},
    UPS.WONDERSWAN_COLOR: {"id": 56, "name": "WonderSwan Color"},
    UPS.X1: {"id": 204, "name": "Sharp X1"},
    UPS.XAVIXPORT: {"id": 170, "name": "XaviXPORT"},
    UPS.XBOX: {"id": 18, "name": "Microsoft Xbox"},
    UPS.XBOX360: {"id": 19, "name": "Microsoft Xbox 360"},
    UPS.XBOXONE: {"id": 20, "name": "Microsoft Xbox One"},
    UPS.ZINC: {"id": 155, "name": "ZiNc"},
    UPS.ZOD: {"id": 75, "name": "Tapwave Zodiac"},
    UPS.ZX81: {"id": 147, "name": "Sinclair ZX-81"},
    UPS.ZXS: {"id": 46, "name": "Sinclair ZX Spectrum"},
}


# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}
