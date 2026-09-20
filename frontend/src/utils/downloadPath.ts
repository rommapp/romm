import type { SimpleRom } from "@/stores/roms";

/** Build the `/api` path that serves a ROM's content. */
export function getDownloadPath({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  const queryParams = new URLSearchParams();
  if (fileIDs.length > 0) {
    queryParams.append("file_ids", fileIDs.join(","));
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
  const contentName = contentFile
    ? encodeURIComponent(contentFile.file_name)
    : rom.fs_name;

  return `/api/roms/${rom.id}/content/${contentName}${
    queryString ? `?${queryString}` : ""
  }`;
}

export function getDownloadLink({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  return `${window.location.origin}${encodeURI(
    getDownloadPath({ rom, fileIDs }),
  )}`;
}
