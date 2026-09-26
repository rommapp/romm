import type { RomFileSchema } from "@/__generated__";

export function romFileUrl(fileId: number, fileName: string): string {
  return `/api/roms/${fileId}/files/content/${encodeURIComponent(fileName)}`;
}

// Keyed on the file's own timestamp: a rescan that replaces the file on disk
// bumps its row without necessarily touching the ROM.
export function versionedRomFileUrl(file: RomFileSchema): string {
  return `${romFileUrl(file.id, file.file_name)}?v=${encodeURIComponent(file.updated_at)}`;
}
