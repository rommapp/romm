// Resolves the art assets attached to a ROM into a flat, display-ready list.
// Shared by the Media tab's Artwork subtab (full gallery) and the Overview tab
// (videos only) so both stay in sync.
//
// Two sources feed the list:
//   1. Scraped resources — ScreenScraper is the richest and wins; gamelist
//      fills in for the few types it also scrapes (mirrors v1's MediaCarousel
//      fallbacks).
//   2. Library media files — images/videos that live in the game folder on
//      disk (rom.files), so a trailer or artwork dropped next to the ROM shows
//      up here too.
//
// Covers, screenshots, the manual and the soundtrack are intentionally left
// out: they each have their own surface elsewhere in the details view.
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

export type RomArtworkEntry = {
  key: string;
  /** i18n key (under the `rom` namespace) for a scraped asset's label. */
  labelKey?: string;
  /** Ready-to-display label for a library file (its name, extension stripped). */
  label?: string;
  url: string;
  isVideo: boolean;
};

// Library file extensions the browser can render inline. Kept in sync with the
// backend download endpoint (utils/media_types.py), which serves these inline.
const LIBRARY_IMAGE_EXTENSIONS = new Set([
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "bmp",
  "avif",
]);
const LIBRARY_VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv", "mov", "m4v"]);

// File categories that already have their own surface in the details view, so
// they must not be duplicated into the artwork gallery.
const SURFACED_ELSEWHERE = new Set(["screenshot", "soundtrack", "manual"]);

export function resolveRomArtwork(rom: DetailedRom): RomArtworkEntry[] {
  const ss = rom.ss_metadata;
  const gl = rom.gamelist_metadata;
  const cacheBust = encodeURIComponent(rom.updated_at);

  const images: { key: string; labelKey: string; path?: string | null }[] = [
    {
      key: "title_screen",
      labelKey: "rom.media-title-screen",
      path: ss?.title_screen_path,
    },
    { key: "logo", labelKey: "rom.media-logo", path: ss?.logo_path },
    {
      key: "marquee",
      labelKey: "rom.media-marquee",
      path: ss?.marquee_path ?? gl?.marquee_path,
    },
    { key: "bezel", labelKey: "rom.media-bezel", path: ss?.bezel_path },
    { key: "fanart", labelKey: "rom.media-fanart", path: ss?.fanart_path },
    {
      key: "box3d",
      labelKey: "rom.media-box3d",
      path: ss?.box3d_path ?? gl?.box3d_path,
    },
    {
      key: "box2d_back",
      labelKey: "rom.media-box2d-back",
      path: ss?.box2d_back_path,
    },
    {
      key: "box2d_side",
      labelKey: "rom.media-box2d-side",
      path: ss?.box2d_side_path,
    },
    {
      key: "physical",
      labelKey: "rom.media-physical",
      path: ss?.physical_path ?? gl?.physical_path,
    },
    {
      key: "miximage",
      labelKey: "rom.media-miximage",
      path: ss?.miximage_path ?? gl?.miximage_path,
    },
    {
      key: "miximage_v2",
      labelKey: "rom.media-miximage-v2",
      path: ss?.miximage_v2_path,
    },
  ];

  const videos: { key: string; labelKey: string; path?: string | null }[] = [
    { key: "video", labelKey: "rom.media-video", path: rom.path_video },
    {
      key: "video_normalized",
      labelKey: "rom.media-video-normalized",
      path: ss?.video_normalized_path,
    },
  ];

  const out: RomArtworkEntry[] = [];
  const seen = new Set<string>();

  const collect = (
    defs: { key: string; labelKey: string; path?: string | null }[],
    isVideo: boolean,
  ) => {
    for (const def of defs) {
      if (!def.path || seen.has(def.path)) continue;
      seen.add(def.path);
      out.push({
        key: def.key,
        labelKey: def.labelKey,
        url: `${FRONTEND_RESOURCES_PATH}/${def.path}?v=${cacheBust}`,
        isVideo,
      });
    }
  };

  // Media files sitting in the game folder. Skip anything that already has its
  // own surface (screenshots / soundtrack / manual); everything else with a
  // known image/video extension is shown alongside the scraped assets.
  const libraryImages: RomArtworkEntry[] = [];
  const libraryVideos: RomArtworkEntry[] = [];
  for (const file of rom.files ?? []) {
    if (file.category && SURFACED_ELSEWHERE.has(file.category)) continue;
    const ext = file.file_name.split(".").pop()?.toLowerCase() ?? "";
    const isVideo = LIBRARY_VIDEO_EXTENSIONS.has(ext);
    if (!isVideo && !LIBRARY_IMAGE_EXTENSIONS.has(ext)) continue;
    (isVideo ? libraryVideos : libraryImages).push({
      key: `file-${file.id}`,
      label: file.file_name.replace(/\.[^.]+$/, ""),
      url: `/api/roms/${file.id}/files/content/${encodeURIComponent(
        file.file_name,
      )}?v=${cacheBust}`,
      isVideo,
    });
  }

  collect(images, false);
  out.push(...libraryImages);
  collect(videos, true);
  out.push(...libraryVideos);
  return out;
}
