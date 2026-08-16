// Choosing which firmware (BIOS) the EmulatorJS player boots with.
//
// A scan flags firmware whose file vanished with `missing_from_fs`, but the
// player used to offer every entry for the platform, and auto-selected the sole
// entry when there was only one. A stale sole entry then made the game fail to
// load with nothing pointing at the BIOS (issue #4075). Missing entries are
// never selectable here, so a platform whose only BIOS is gone boots with none
// rather than with a file the server can't serve.

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
  // `bios_file` from the selected core's EJS config. Typed as the config's
  // own `string | boolean` since most EJS settings are toggles; only a
  // string names a file.
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
