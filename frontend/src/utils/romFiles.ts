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

const IMAGE_DOC_EXTENSIONS: ReadonlySet<string> = new Set(["cbz", "cbr"]);

/** Whether a document is an image doc (.cbz/.cbr), paged by ImageDocViewer. */
export function isImageDoc(name: string): boolean {
  return IMAGE_DOC_EXTENSIONS.has(fileExtension(name.split("?")[0] ?? ""));
}

/** API path (below `/api`) of an image doc's pages: a rom file's, or the ROM's
 *  scraped manual's when there is no file. */
export function imageDocPagesPath(
  romId: number,
  fileId: number | null,
): string {
  return fileId == null
    ? `/roms/${romId}/manuals/pages`
    : `/roms/${romId}/files/${fileId}/pages`;
}

/** Image URL of an image doc's 1-based page, keyed on the document's version. */
export function imageDocPageUrl(
  pagesPath: string,
  page: number,
  version: string,
): string {
  return `/api${pagesPath}/${page}?v=${encodeURIComponent(version)}`;
}
