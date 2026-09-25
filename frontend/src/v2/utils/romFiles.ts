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

/** Whether the ROM is a disc in its own folder with a cue sheet to read tracks from. */
export function hasCueSheet(rom: DetailedRom): boolean {
  return (
    !rom.has_simple_single_file &&
    (rom.files ?? []).some(
      (file) =>
        (file.category == null || file.category === "game") &&
        file.file_name.toLowerCase().endsWith(".cue"),
    )
  );
}
