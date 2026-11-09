import type { RomFileCategory } from "@/__generated__";

// Kept in step with SUPPORTED_PATCH_EXTENSIONS in backend/utils/rom_patcher/patcher.py.
export const SUPPORTED_PATCH_EXTENSIONS: readonly string[] = [
  ".ips",
  ".ups",
  ".bps",
  ".ppf",
  ".rup",
  ".aps",
  ".bdf",
  ".pmsr",
  ".vcdiff",
  ".xdelta",
];

export function fileExtension(name: string): string {
  const match = name.match(/\.[^.]+$/);
  return match ? match[0].toLowerCase() : "";
}

/** A patch file, by its folder or, wherever it sits, by its extension. */
export function isPatchFile(file: {
  file_name: string;
  category?: RomFileCategory | null;
}): boolean {
  return (
    file.category === "patch" ||
    SUPPORTED_PATCH_EXTENSIONS.includes(fileExtension(file.file_name))
  );
}
