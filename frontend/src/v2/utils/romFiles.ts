import type { RomFileSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";

export function romFileUrl(fileId: number, fileName: string): string {
  return `/api/roms/${fileId}/files/content/${encodeURIComponent(fileName)}`;
}

// Keyed on the file's own timestamp: a rescan that replaces the file on disk
// bumps its row without necessarily touching the ROM.
export function versionedRomFileUrl(file: RomFileSchema): string {
  return `${romFileUrl(file.id, file.file_name)}?v=${encodeURIComponent(file.updated_at)}`;
}

/** Whether the ROM has a disc image to read CD audio tracks from: a CHD, or a
 * cue sheet in a folder of its own (a lone one would lose its tracks). */
export function hasDiscImage(rom: DetailedRom): boolean {
  return (rom.files ?? []).some((file) => {
    if (file.category != null && file.category !== "game") return false;
    const name = file.file_name.toLowerCase();
    return (
      name.endsWith(".chd") ||
      (name.endsWith(".cue") && !rom.has_simple_single_file)
    );
  });
}
