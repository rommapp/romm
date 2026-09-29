// What the Overview tab shows: the user's pinned media, or a default
// selection (screenshots and videos) until they pin or unpin anything.
import type { RomFileSchema } from "@/__generated__";
import i18n from "@/locales";
import type { DetailedRom } from "@/stores/roms";
import type { MediaShelfItem } from "@/v2/components/GameDetails/MediaShelf.vue";
import { mediaKey } from "@/v2/utils/mediaKeys";
import { resolveRomArtwork } from "@/v2/utils/romArtwork";
import { versionedRomFileUrl } from "@/v2/utils/romFiles";

// Mirrors PINNED_MEDIA_MAX_ITEMS in backend/models/rom.py.
export const PINNED_MEDIA_MAX_ITEMS = 100;

// Previewable image extensions for screenshots in the game folder. Mirrors
// the canonical "Web Images" set.
const SCREENSHOT_EXTENSIONS = new Set([
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "bmp",
  "avif",
]);

export function romFolderScreenshots(rom: DetailedRom): RomFileSchema[] {
  return (rom.files ?? []).filter((file) => {
    const rel = file.full_path.replace(rom.full_path, "").replace(/^\//, "");
    const firstSegment = rel.split("/")[0]?.toLowerCase();
    if (firstSegment !== "screenshots" && firstSegment !== "screenshot") {
      return false;
    }
    const ext = file.file_name.split(".").pop()?.toLowerCase() ?? "";
    return SCREENSHOT_EXTENSIONS.has(ext);
  });
}

function screenshotItems<T>(
  list: T[],
  keyOf: (entry: T) => string,
  urlOf: (entry: T) => string,
): MediaShelfItem[] {
  return list.map((entry, i) => ({
    key: keyOf(entry),
    label: i18n.global.t("rom.screenshot-num", { n: i + 1 }),
    url: urlOf(entry),
  }));
}

function mediaSources(rom: DetailedRom) {
  return {
    screenshots: [
      ...screenshotItems(
        rom.merged_screenshots ?? [],
        mediaKey.scraped,
        (url) => url,
      ),
      ...screenshotItems(
        romFolderScreenshots(rom),
        (file) => mediaKey.file(file.id),
        versionedRomFileUrl,
      ),
    ],
    userScreenshots: screenshotItems(
      rom.all_user_screenshots ?? [],
      (shot) => mediaKey.screenshot(shot.id),
      (shot) => shot.download_path,
    ),
    artwork: resolveRomArtwork(rom),
  };
}

// Capped so the first toggle can always save the defaults it starts from.
function defaultKeys({
  screenshots,
  artwork,
}: ReturnType<typeof mediaSources>): string[] {
  return [...screenshots, ...artwork.filter((entry) => entry.isVideo)]
    .map((item) => item.key)
    .slice(0, PINNED_MEDIA_MAX_ITEMS);
}

export function defaultPinnedMediaKeys(rom: DetailedRom): string[] {
  return defaultKeys(mediaSources(rom));
}

export function pinnedMediaKeys(rom: DetailedRom): string[] {
  return rom.rom_user?.pinned_media ?? defaultPinnedMediaKeys(rom);
}

// Keys whose media is gone (a rescrape, a deleted file, a screenshot made
// private) are skipped rather than pruned, so they return with the media.
export function resolvePinnedMedia(rom: DetailedRom): MediaShelfItem[] {
  const sources = mediaSources(rom);
  const byKey = new Map(
    [
      ...sources.screenshots,
      ...sources.userScreenshots,
      ...sources.artwork,
    ].map((item) => [item.key, item]),
  );
  const keys = rom.rom_user?.pinned_media ?? defaultKeys(sources);
  return keys.flatMap((key) => byKey.get(key) ?? []);
}

export function togglePinnedMediaKey(keys: string[], key: string): string[] {
  return keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key];
}
