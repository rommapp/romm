import type { RomFileSchema } from "@/__generated__";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

/** A file name's last extension, lowercased and without the dot ("" when it has none). */
export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

export function romFileUrl(fileId: number, fileName: string): string {
  return `/api/roms/${fileId}/files/content/${encodeURIComponent(fileName)}`;
}

// Keyed on the file's own timestamp: a rescan that replaces the file on disk
// bumps its row without necessarily touching the ROM.
export function versionedRomFileUrl(file: RomFileSchema): string {
  return `${romFileUrl(file.id, file.file_name)}?v=${encodeURIComponent(file.updated_at)}`;
}

// Scraped media is keyed on the ROM's timestamp, which a metadata refresh bumps.
export function versionedResourceUrl(
  path: string,
  romUpdatedAt: string,
): string {
  return `${FRONTEND_RESOURCES_PATH}/${path}?v=${encodeURIComponent(romUpdatedAt)}`;
}
