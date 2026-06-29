// Resolves the scraped art assets attached to a ROM into a flat, display-ready
// list. Shared by the Media tab's Artwork subtab (full gallery) and the
// Overview tab (videos only) so both stay in sync.
//
// Covers, screenshots, the manual and the soundtrack are intentionally left
// out: they each have their own surface elsewhere in the details view.
// ScreenScraper is the richest source and wins; gamelist fills in for the few
// types it also scrapes (mirrors v1's MediaCarousel fallbacks).
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

export type RomArtworkEntry = {
  key: string;
  /** i18n key (under the `rom` namespace) for the asset's display label. */
  labelKey: string;
  url: string;
  isVideo: boolean;
};

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

  collect(images, false);
  collect(videos, true);
  return out;
}
