from pathlib import Path
from typing import TYPE_CHECKING

from config.config_manager import MetadataMediaType
from handler.filesystem import fs_resource_handler
from handler.metadata.ss_handler import get_preferred_media_types
from utils.database import safe_str_to_bool

if TYPE_CHECKING:
    from models.rom import Rom

from .types import (
    LAUNCHBOX_IMAGES_DIR,
    LAUNCHBOX_MANUALS_DIR,
    LAUNCHBOX_VIDEOS_DIR,
    LaunchboxImage,
    LaunchboxMetadata,
    LaunchboxRom,
    LocalMediaContext,
    MediaRequest,
)
from .utils import (
    coalesce,
    dedupe_words,
    file_uri_for_local_path,
    parse_list,
    parse_playmode,
    parse_release_date,
    parse_videourl,
    sanitize_filename,
)

VIDEO_EXTS: tuple[str, ...] = (".mp4", ".webm", ".avi", ".mkv", ".mov", ".wmv")


def local_media_req(
    *,
    platform_name: str | None,
    fs_name: str,
    local: dict[str, str] | None,
    remote: dict | None,
    remote_images: list[dict] | None,
    remote_enabled: bool,
) -> MediaRequest:
    title = ((local or {}).get("Title") or "").strip()
    region_hint = ((local or {}).get("Region") or "").strip() or None
    return MediaRequest(
        platform_name,
        fs_name,
        title,
        region_hint,
        remote_images,
        remote_enabled,
    )


def remote_media_req(
    *,
    remote: dict | None,
    remote_images: list[dict] | None,
    remote_enabled: bool,
    platform_name: str | None = None,
    fs_name: str = "",
) -> MediaRequest:
    title = ((remote or {}).get("Name") or "").strip()
    # Without a platform_name, _build_local_media_context bails and local
    # Images/Manuals/Videos never get searched. Fall back to the platform
    # recorded on the remote entry so remote-matched ROMs can still surface
    # on-disk media.
    if not platform_name and remote:
        platform_name = (remote.get("Platform") or "").strip() or None
    return MediaRequest(
        platform_name,
        fs_name,
        title,
        None,
        remote_images,
        remote_enabled,
    )


def _build_local_media_context(
    req: MediaRequest,
    base_dir: Path,
    *,
    include_region_hints: bool = True,
) -> LocalMediaContext | None:
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
        clean = sanitize_filename(s)
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
    ctx: LocalMediaContext,
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

        try:
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
        except (OSError, PermissionError):
            return []

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


def _get_cover(req: MediaRequest) -> str | None:
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

    # Remote media (overridden by local if available)
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
            url = file_uri_for_local_path(cover_path)
            if url:
                cover = url
                break

    return cover


def _get_screenshots(req: MediaRequest) -> list[str]:
    screenshots: list[str] = []

    # Remote media (overridden by local if available)
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
                url = file_uri_for_local_path(p)
                if url and url not in seen:
                    seen.add(url)
                    local_screens.append(url)

        if local_screens:
            screenshots = local_screens

    return screenshots


def _get_manuals(req: MediaRequest) -> str | None:
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
        return sanitize_filename(p.stem).lower()

    pdfs_sorted = sorted(pdfs, key=lambda p: (len(p.name), p.name.lower()))

    stems_lower = [s.lower() for s in ctx["stems"]]

    for stem in stems_lower:
        for p in pdfs_sorted:
            if _key(p) == stem:
                url = file_uri_for_local_path(p)
                if url:
                    return url

    for stem in stems_lower:
        for p in pdfs_sorted:
            if _key(p).startswith(stem):
                url = file_uri_for_local_path(p)
                if url:
                    return url

    return manual


def _get_video(req: MediaRequest) -> str | None:
    """Resolve a local LaunchBox video for the given ROM.

    LaunchBox stores videos flat under `Videos/<Platform>/<GameStem>.<ext>`
    (no region or category subdirectories). Return a `launchbox-file://` URL
    to the first match, or None.
    """
    ctx = _build_local_media_context(
        req, LAUNCHBOX_VIDEOS_DIR, include_region_hints=False
    )
    if ctx is None:
        return None

    for stem in ctx["stems"]:
        for ext in VIDEO_EXTS:
            candidate = ctx["base"] / f"{stem}{ext}"
            if candidate.is_file():
                return file_uri_for_local_path(candidate)

    return None


def _get_images(req: MediaRequest) -> list[LaunchboxImage]:
    images: list[LaunchboxImage] = []

    # Remote media (overridden by local if available)
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
                url = file_uri_for_local_path(p)
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


def build_launchbox_metadata(
    *,
    local: dict[str, str] | None = None,
    remote: dict | None = None,
    images: list[LaunchboxImage],
) -> LaunchboxMetadata:
    local_release_date = local.get("ReleaseDate") if local else None
    remote_release_date = remote.get("ReleaseDate") if remote else None
    release_date_raw = coalesce(local_release_date, remote_release_date)
    first_release_date = parse_release_date(release_date_raw)

    max_players_raw = coalesce(
        local.get("MaxPlayers") if local else None,
        remote.get("MaxPlayers") if remote else None,
    )
    try:
        max_players = int(max_players_raw or 0)
    except (TypeError, ValueError):
        max_players = 0

    release_type = (
        coalesce(
            local.get("ReleaseType") if local else None,
            remote.get("ReleaseType") if remote else None,
        )
        or ""
    )

    if local and coalesce(local.get("PlayMode")):
        cooperative = parse_playmode(local.get("PlayMode"))
    else:
        cooperative = safe_str_to_bool(
            (remote.get("Cooperative") if remote else None) or "false"
        )

    video_url = coalesce(
        (local.get("VideoUrl") if local else None),
        (remote.get("VideoURL") if remote else None),
    )

    community_rating_raw = coalesce(
        local.get("CommunityStarRating") if local else None,
        remote.get("CommunityRating") if remote else None,
    )
    try:
        community_rating = float(community_rating_raw or 0.0)
    except (TypeError, ValueError):
        community_rating = 0.0

    community_rating_count_raw = coalesce(
        local.get("CommunityStarRatingTotalVotes") if local else None,
        remote.get("CommunityRatingCount") if remote else None,
    )
    try:
        community_rating_count = int(community_rating_count_raw or 0)
    except (TypeError, ValueError):
        community_rating_count = 0

    wikipedia_url = (
        coalesce(
            local.get("WikipediaURL") if local else None,
            remote.get("WikipediaURL") if remote else None,
        )
        or ""
    )

    esrb_raw = coalesce(
        (local.get("Rating") if local else None),
        (remote.get("ESRB") if remote else None),
    )
    esrb = (esrb_raw or "").split(" - ")[0].strip()

    genres_raw = coalesce(
        local.get("Genre") if local else None,
        remote.get("Genres") if remote else None,
    )
    genres = parse_list(genres_raw)

    publisher = coalesce(
        local.get("Publisher") if local else None,
        remote.get("Publisher") if remote else None,
    )
    developer = coalesce(
        local.get("Developer") if local else None,
        remote.get("Developer") if remote else None,
    )
    companies = dedupe_words([publisher, developer])

    return LaunchboxMetadata(
        {
            "first_release_date": first_release_date,
            "max_players": max_players,
            "release_type": release_type,
            "cooperative": cooperative,
            "youtube_video_id": parse_videourl(video_url),
            "community_rating": community_rating,
            "community_rating_count": community_rating_count,
            "wikipedia_url": wikipedia_url,
            "esrb": esrb,
            "genres": genres,
            "companies": companies,
            "images": images,
        }
    )


def populate_rom_specific_paths(
    metadata: LaunchboxMetadata, rom: "Rom"
) -> LaunchboxMetadata:
    """Populate rom-specific media paths on a LaunchBox metadata dict.

    Called after the Rom is known (in the scan pipeline) to compute the
    destination path for local media that the handler surfaced a URL for.
    Currently just covers video.
    """
    if (
        MetadataMediaType.VIDEO in get_preferred_media_types()
        and "video_url" in metadata
        and metadata.get("video_url")
    ):
        base = fs_resource_handler.get_media_resources_path(
            rom.platform_id, rom.id, MetadataMediaType.VIDEO
        )
        ext = Path(metadata["video_url"]).suffix.lower()
        if ext not in VIDEO_EXTS:
            ext = ".mp4"
        metadata["video_path"] = f"{base}/video{ext}"
    return metadata


def build_rom(
    *,
    local: dict[str, str] | None,
    remote: dict | None,
    launchbox_id: int | None,
    media_req: MediaRequest | None = None,
) -> LaunchboxRom:
    images: list[LaunchboxImage] = (
        _get_images(media_req) if media_req is not None else []
    )

    url_cover: str | None = None
    url_screenshots: list[str] = []
    url_manual: str | None = None
    video_url: str | None = None
    if media_req is not None:
        url_cover = _get_cover(media_req)
        url_screenshots = _get_screenshots(media_req)
        url_manual = _get_manuals(media_req)
        video_url = _get_video(media_req)
    url_screenshots = url_screenshots or []

    name = (
        coalesce(
            (local.get("Title") if local else None),
            (remote.get("Name") if remote else None),
        )
        or ""
    ).strip()

    summary = (
        coalesce(
            (local.get("Notes") if local else None),
            (remote.get("Overview") if remote else None),
        )
        or ""
    ).strip()

    launchbox_id = int(launchbox_id) if launchbox_id is not None else None
    metadata = build_launchbox_metadata(
        local=local,
        remote=remote,
        images=images,
    )
    if video_url:
        metadata["video_url"] = video_url
    return LaunchboxRom(
        launchbox_id=launchbox_id,
        name=name,
        summary=summary,
        url_cover=url_cover or "",
        url_screenshots=url_screenshots,
        url_manual=url_manual or "",
        launchbox_metadata=metadata,
    )
