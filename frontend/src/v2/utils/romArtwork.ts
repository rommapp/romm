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
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

export type RomArtworkEntry = {
  key: string;
  label: string;
  url: string;
  isVideo?: boolean;
};

// Library file extensions the browser can render inline. Kept in sync with the
// backend download endpoint (utils/media_types.py), which serves these inline.
const LIBRARY_IMAGE_EXTENSIONS = new Set([
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "tiff",
  "tif",
  "bmp",
  "avif",
]);
const LIBRARY_VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv", "mov", "m4v"]);

// File categories that already have their own surface in the details view, so
// they must not be duplicated into the artwork gallery.
const SURFACED_ELSEWHERE = new Set(["screenshot", "soundtrack", "manual"]);

export function resolveRomArtwork(rom: DetailedRom): RomArtworkEntry[] {
  const { t } = useI18n();

  const ss = rom.ss_metadata;
  const gl = rom.gamelist_metadata;
  const cacheBust = encodeURIComponent(rom.updated_at);
  const seen = new Set<string>();
  const out: RomArtworkEntry[] = [];

  const artworkDefs: (Omit<RomArtworkEntry, "url"> & { url: string | null })[] =
    [
      {
        key: "title_screen",
        label: t("rom.media-title-screen"),
        url: ss?.title_screen_path ?? null,
      },
      { key: "logo", label: t("rom.media-logo"), url: ss?.logo_path ?? null },
      {
        key: "marquee",
        label: t("rom.media-marquee"),
        url: ss?.marquee_path ?? gl?.marquee_path ?? null,
      },
      {
        key: "bezel",
        label: t("rom.media-bezel"),
        url: ss?.bezel_path ?? null,
      },
      {
        key: "fanart",
        label: t("rom.media-fanart"),
        url: ss?.fanart_path ?? null,
      },
      {
        key: "box3d",
        label: t("rom.media-box3d"),
        url: ss?.box3d_path ?? gl?.box3d_path ?? null,
      },
      {
        key: "box2d_back",
        label: t("rom.media-box2d-back"),
        url: ss?.box2d_back_path ?? null,
      },
      {
        key: "box2d_side",
        label: t("rom.media-box2d-side"),
        url: ss?.box2d_side_path ?? null,
      },
      {
        key: "physical",
        label: t("rom.media-physical"),
        url: ss?.physical_path ?? gl?.physical_path ?? null,
      },
      {
        key: "miximage",
        label: t("rom.media-miximage"),
        url: ss?.miximage_path ?? gl?.miximage_path ?? null,
      },
      {
        key: "miximage_v2",
        label: t("rom.media-miximage-v2"),
        url: ss?.miximage_v2_path ?? null,
      },
      {
        key: "video",
        label: t("rom.media-video"),
        url: rom.path_video ?? null,
        isVideo: true,
      },
      {
        key: "video_normalized",
        label: t("rom.media-video-normalized"),
        url: ss?.video_normalized_path ?? null,
        isVideo: true,
      },
    ];

  const libraryMedia = rom.files
    .filter((file) => !file.category || !SURFACED_ELSEWHERE.has(file.category))
    .map((file) => {
      const ext = file.file_name.split(".").pop()?.toLowerCase() ?? "";
      const isVideo = LIBRARY_VIDEO_EXTENSIONS.has(ext);
      if (!isVideo && !LIBRARY_IMAGE_EXTENSIONS.has(ext)) return null;

      return {
        key: `file-${file.id}`,
        label: file.file_name.replace(/\.[^.]+$/, ""),
        url: `/api/roms/${file.id}/files/content/${encodeURIComponent(file.file_name)}?v=${cacheBust}`,
        isVideo,
      };
    })
    .filter((entry) => entry !== null);

  for (const def of artworkDefs) {
    if (!def.url || seen.has(def.url)) continue;
    seen.add(def.url);
    out.push({
      key: def.key,
      label: def.label,
      url: `${FRONTEND_RESOURCES_PATH}/${def.url}?v=${cacheBust}`,
      isVideo: def.isVideo ?? false,
    });
  }

  return [...out, ...libraryMedia];
}
