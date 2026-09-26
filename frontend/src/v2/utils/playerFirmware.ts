// Which firmware (BIOS) the EmulatorJS player boots with. Missing entries are
// never selectable, so a platform whose only BIOS is gone boots with none.

// Only these fields are read, so both `FirmwareSchema` and lighter shapes fit.
interface FirmwareLike {
  id: number;
  file_name: string;
  missing_from_fs: boolean;
}

export function resolveInitialFirmware<T extends FirmwareLike>({
  options,
  storedBiosId,
  configBiosFile,
}: {
  options: readonly T[];
  // The user's last pick for this platform, from localStorage.
  storedBiosId: string | null;
  // `bios_file` from the core's EJS config, typed `string | boolean` because
  // most EJS settings are toggles; only a string names a file.
  configBiosFile: string | boolean | undefined;
}): T | null {
  const usable = options.filter((f) => !f.missing_from_fs);

  const fromStorage = storedBiosId
    ? usable.find((f) => f.id === parseInt(storedBiosId))
    : undefined;
  const fromConfig =
    typeof configBiosFile === "string"
      ? usable.find((f) => f.file_name === configBiosFile)
      : undefined;
  // Auto-select only when the choice is unambiguous.
  const fromSingleOption = usable.length === 1 ? usable[0] : undefined;

  return fromStorage ?? fromConfig ?? fromSingleOption ?? null;
}

const SYSTEM_DIRECTORY = "/home/web_user/retroarch/userdata/system";
const UNSAFE_FILE_NAME = /^\.{1,2}$|[\\/]/;
// EJS_externalFiles writes an archive to a file key raw (4.2.3) or as its first
// entry (nightly), so archives keep loading through EJS_biosUrl.
const ARCHIVE_EXTENSION = /\.(zip|7z|rar)$/i;

/** Every platform firmware file for PUAE, as EJS_externalFiles entries. */
export function firmwareExternalFiles(
  core: string,
  firmware: readonly FirmwareLike[],
): Record<string, string> {
  // PUAE picks among several Kickstarts by name for each game.
  if (core !== "puae") return {};

  return Object.fromEntries(
    firmware
      .filter(
        ({ file_name, missing_from_fs }) =>
          !missing_from_fs &&
          !UNSAFE_FILE_NAME.test(file_name) &&
          !ARCHIVE_EXTENSION.test(file_name),
      )
      .map(({ id, file_name }) => [
        `${SYSTEM_DIRECTORY}/${file_name}`,
        `/api/firmware/${id}/content/${encodeURIComponent(file_name)}`,
      ]),
  );
}
