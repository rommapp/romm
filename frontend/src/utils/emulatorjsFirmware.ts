import type { FirmwareLike } from "@/v2/utils/playerFirmware";

const SYSTEM_DIRECTORY = "/home/web_user/retroarch/userdata/system";
// Cores that pick among several firmware files by name for each game.
const FILENAME_SELECTING_CORES = new Set(["puae"]);
// EJS_externalFiles writes an archive to a file key raw (4.2.3) or as its first
// entry (nightly), so archives keep loading through EJS_biosUrl.
const ARCHIVE_EXTENSION = /\.(zip|7z|rar)$/i;

/** Every platform firmware file for a filename-selecting core, as EJS_externalFiles entries. */
export function firmwareExternalFiles(
  core: string,
  firmware: readonly FirmwareLike[],
): Record<string, string> {
  if (!FILENAME_SELECTING_CORES.has(core)) return {};

  return Object.fromEntries(
    firmware
      .filter(
        ({ file_name, missing_from_fs }) =>
          !missing_from_fs &&
          file_name !== "." &&
          file_name !== ".." &&
          !/[\\/]/.test(file_name) &&
          !ARCHIVE_EXTENSION.test(file_name),
      )
      .map(({ id, file_name }) => [
        `${SYSTEM_DIRECTORY}/${file_name}`,
        `/api/firmware/${id}/content/${encodeURIComponent(file_name)}`,
      ]),
  );
}
