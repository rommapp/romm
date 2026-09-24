// What the Overview tab shows: the user's pinned media, or a default
// selection (screenshots and videos) until they pin or unpin anything.
import type { RomFileSchema } from "@/__generated__";
import i18n from "@/locales";
import type { DetailedRom } from "@/stores/roms";
import type { MediaShelfItem } from "@/v2/components/GameDetails/MediaShelf.vue";
import { mediaKey } from "@/v2/utils/mediaKeys";
import { resolveRomArtwork } from "@/v2/utils/romArtwork";
import { versionedRomFileUrl } from "@/v2/utils/romFiles";

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

function screenshotLabel(n: number): string {
  return i18n.global.t("rom.screenshot-num", { n });
}

function scrapedScreenshots(rom: DetailedRom): MediaShelfItem[] {
  return (rom.merged_screenshots ?? []).map((url, i) => ({
    key: mediaKey.scraped(url),
    label: screenshotLabel(i + 1),
    url,
  }));
}

function folderScreenshots(rom: DetailedRom): MediaShelfItem[] {
  return romFolderScreenshots(rom).map((file, i) => ({
    key: mediaKey.file(file.id),
    label: screenshotLabel(i + 1),
    url: versionedRomFileUrl(file),
  }));
}

function userScreenshots(rom: DetailedRom): MediaShelfItem[] {
  return (rom.all_user_screenshots ?? []).map((shot, i) => ({
    key: mediaKey.screenshot(shot.id),
    label: screenshotLabel(i + 1),
    url: shot.download_path,
  }));
}

export function defaultPinnedMediaKeys(rom: DetailedRom): string[] {
  return [
    ...scrapedScreenshots(rom),
    ...folderScreenshots(rom),
    ...resolveRomArtwork(rom).filter((entry) => entry.isVideo),
  ].map((item) => item.key);
}

export function pinnedMediaKeys(rom: DetailedRom): string[] {
  return rom.rom_user?.pinned_media ?? defaultPinnedMediaKeys(rom);
}

// Keys whose media is gone (a rescrape, a deleted file, a screenshot made
// private) are skipped rather than pruned, so they return with the media.
export function resolvePinnedMedia(rom: DetailedRom): MediaShelfItem[] {
  const byKey = new Map(
    [
      ...scrapedScreenshots(rom),
      ...folderScreenshots(rom),
      ...userScreenshots(rom),
      ...resolveRomArtwork(rom),
    ].map((item) => [item.key, item]),
  );
  return pinnedMediaKeys(rom).flatMap((key) => byKey.get(key) ?? []);
}

export function togglePinnedMediaKey(keys: string[], key: string): string[] {
  return keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key];
}
