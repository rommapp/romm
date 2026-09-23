interface FirmwareFile {
  id: number;
  file_name: string;
  missing_from_fs: boolean;
}

const SYSTEM_DIRECTORY = "/home/web_user/retroarch/userdata/system";

export function puaeFirmwareFiles(
  core: string,
  firmware: readonly FirmwareFile[],
): Record<string, string> {
  if (core !== "puae") return {};

  return Object.fromEntries(
    firmware
      .filter(
        ({ file_name, missing_from_fs }) =>
          !missing_from_fs &&
          file_name !== "." &&
          file_name !== ".." &&
          !/[\\/]/.test(file_name),
      )
      .map(({ id, file_name }) => [
        `${SYSTEM_DIRECTORY}/${file_name}`,
        `/api/firmware/${id}/content/${encodeURIComponent(file_name)}`,
      ]),
  );
}
