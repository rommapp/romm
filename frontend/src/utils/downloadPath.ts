import type { RomFileSchema } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";

/** Build the `/api` path that serves a ROM's content.
 *  `purpose: "play"` marks a player's fetch, which is logged as a player load. */
export function getDownloadPath({
  rom,
  fileIDs = [],
  purpose,
}: {
  rom: SimpleRom;
  fileIDs?: number[];
  purpose?: "play";
}) {
  const queryParams = new URLSearchParams();
  if (fileIDs.length > 0) {
    queryParams.append("file_ids", fileIDs.join(","));
  }
  if (purpose) {
    queryParams.append("purpose", purpose);
  }
  const queryString = queryParams.toString();

  const selectedFile =
    fileIDs.length === 1
      ? rom.files?.find((f) => f.id === fileIDs[0])
      : undefined;
  const nestedFile =
    fileIDs.length === 0 &&
    rom.has_nested_single_file &&
    rom.files?.length === 1
      ? rom.files[0]
      : undefined;
  const contentFile = selectedFile ?? nestedFile;
  // One path segment, so it is encoded here and never again: callers that
  // prepend an origin must not re-encode. A bare `#` or `%` in a name would
  // otherwise truncate the URL or survive as a literal in the zip's name.
  const contentName = encodeURIComponent(
    contentFile ? contentFile.file_name : rom.fs_name,
  );

  return `/api/roms/${rom.id}/content/${contentName}${
    queryString ? `?${queryString}` : ""
  }`;
}

/** The name the content endpoint serves a whole rom under: the sole file's own
 *  name, or the rom's name with a zip extension, mirroring `get_rom_content`. */
export function getDownloadFileName(rom: SimpleRom): string {
  const files = rom.files ?? [];
  if (files.length === 1) return files[0].file_name;
  // Nothing to serve; callers gate on a file being on disk.
  if (files.length === 0) return rom.fs_name;
  return `${rom.fs_name}.zip`;
}

/** The one file this rom resolves to on disk, or null when it resolves to
 *  several and the endpoint builds an archive instead. */
export function getSoleRomFile(rom: SimpleRom): RomFileSchema | null {
  const files = rom.files ?? [];
  return files.length === 1 ? files[0] : null;
}

export function getDownloadLink({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  return `${window.location.origin}${getDownloadPath({ rom, fileIDs })}`;
}
