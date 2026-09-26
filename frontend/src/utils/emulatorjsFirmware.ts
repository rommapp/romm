import type { FirmwareSchema } from "@/__generated__";

type FirmwareFile = Pick<
  FirmwareSchema,
  "id" | "file_name" | "missing_from_fs"
>;

const SYSTEM_DIRECTORY = "/home/web_user/retroarch/userdata/system";
// Where EmulatorJS writes EJS_biosUrl, next to the game.
const CONTENT_DIRECTORY = "";
// Cores that pick among several firmware files by name for each game.
const FILENAME_SELECTING_CORES = new Set(["puae"]);
// EJS_externalFiles writes archives unextracted; they still load through EJS_biosUrl.
const ARCHIVE_EXTENSION = /\.(zip|7z|rar)$/i;

/** Firmware to load beside EJS_biosUrl: always all for filename-selecting cores, otherwise all only when none is selected. */
export function firmwareExternalFiles(
  core: string,
  firmware: readonly FirmwareFile[],
  selected: FirmwareFile | null,
): Record<string, string> {
  let directory: string;
  if (FILENAME_SELECTING_CORES.has(core)) directory = SYSTEM_DIRECTORY;
  else if (!selected) directory = CONTENT_DIRECTORY;
  else return {};

  return Object.fromEntries(
    firmware
      .filter(
        ({ id, file_name, missing_from_fs }) =>
          id !== selected?.id &&
          !missing_from_fs &&
          file_name !== "." &&
          file_name !== ".." &&
          !/[\\/]/.test(file_name) &&
          !ARCHIVE_EXTENSION.test(file_name),
      )
      .map(({ id, file_name }) => [
        `${directory}/${file_name}`,
        `/api/firmware/${id}/content/${encodeURIComponent(file_name)}`,
      ]),
  );
}
