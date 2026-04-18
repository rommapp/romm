import type { StateSchema } from "@/__generated__";
import stateApi from "@/services/api/state";
import { type DetailedRom } from "@/stores/roms";

const EMULATOR_NAME = "js-dos";

function buildStateName(rom: DetailedRom): string {
  const romName = rom.fs_name_no_ext.trim();
  return `${romName} [${new Date().toISOString().replace(/[:.]/g, "-").replace("T", " ").replace("Z", "")}]`;
}

export async function saveJsDosState({
  rom,
  stateFile,
}: {
  rom: DetailedRom;
  stateFile: Uint8Array;
}): Promise<StateSchema | null> {
  const filename = buildStateName(rom);
  try {
    const uploadedStates = await stateApi.uploadStates({
      rom: rom,
      emulator: EMULATOR_NAME,
      statesToUpload: [
        {
          stateFile: new File(
            [new Uint8Array(stateFile)],
            `${filename}.state`,
            { type: "application/octet-stream" },
          ),
        },
      ],
    });

    const uploadedState = uploadedStates[0];
    if (uploadedState.status === "fulfilled") {
      rom.user_states.unshift(uploadedState.value);
      return uploadedState.value;
    }
  } catch (error) {
    console.error("Failed to upload js-dos state:", error);
  }
  return null;
}
