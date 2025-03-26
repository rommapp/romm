import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import { type DetailedRom } from "@/stores/roms";
import { type SaveSchema } from "@/__generated__";
import { type StateSchema } from "@/__generated__";

function buildStateName(rom: DetailedRom): string {
  const romName = rom.fs_name_no_ext.trim();
  return `${romName} [${new Date().toISOString().replace(/[:.]/g, "-").replace("T", " ").replace("Z", "")}].state`;
}

function buildSaveName(rom: DetailedRom): string {
  const romName = rom.fs_name_no_ext.trim();
  return `${romName} [${new Date().toISOString().replace(/[:.]/g, "-").replace("T", " ").replace("Z", "")}].srm`;
}

export async function saveState({
  rom,
  stateFile,
  screenshotFile,
}: {
  rom: DetailedRom;
  stateFile: Uint8Array;
  screenshotFile?: Uint8Array;
}): Promise<StateSchema | null> {
  const uploadedStates = await stateApi.uploadStates({
    rom: rom,
    emulator: window.EJS_core,
    statesToUpload: [
      {
        stateFile: new File([stateFile], buildStateName(rom), {
          type: "application/octet-stream",
        }),
        screenshotFile: screenshotFile
          ? new File([screenshotFile], buildSaveName(rom), {
              type: "application/octet-stream",
            })
          : undefined,
      },
    ],
  });

  const uploadedState = uploadedStates[0];
  if (uploadedState.status == "fulfilled") {
    if (rom) rom.user_states.push(uploadedState.value);
    return uploadedState.value;
  }

  return null;
}

export async function saveSave({
  rom,
  saveFile,
  screenshotFile,
}: {
  rom: DetailedRom;
  saveFile: Uint8Array;
  screenshotFile?: Uint8Array;
}): Promise<SaveSchema | null> {
  const uploadedSaves = await saveApi.uploadSaves({
    rom: rom,
    emulator: window.EJS_core,
    savesToUpload: [
      {
        saveFile: new File([saveFile], buildSaveName(rom), {
          type: "application/octet-stream",
        }),
        screenshotFile: screenshotFile
          ? new File([screenshotFile], buildSaveName(rom), {
              type: "application/octet-stream",
            })
          : undefined,
      },
    ],
  });

  const uploadedSave = uploadedSaves[0];
  if (uploadedSave.status == "fulfilled") {
    if (rom) rom.user_saves.push(uploadedSave.value);
    return uploadedSave.value;
  }

  return null;
}
