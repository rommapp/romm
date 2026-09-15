import type { RomFileSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";

export function romFileScreenshotUrl(
  file: RomFileSchema,
  updatedAt: string,
): string {
  return `/api/roms/${file.id}/files/content/${encodeURIComponent(file.file_name)}?v=${encodeURIComponent(updatedAt)}`;
}

export function overviewScreenshotUrls(rom: DetailedRom): string[] {
  return [
    ...(rom.merged_screenshots ?? []),
    ...(rom.files ?? [])
      .filter((file) => file.category === "screenshot" && file.is_on_overview)
      .map((file) => romFileScreenshotUrl(file, rom.updated_at)),
  ].filter((url, index, urls) => urls.indexOf(url) === index);
}
