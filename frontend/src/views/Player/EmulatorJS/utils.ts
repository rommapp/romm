import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import { type DetailedRom } from "@/stores/roms";
import { type SaveSchema } from "@/__generated__";
import { type StateSchema } from "@/__generated__";

function buildStateName(rom: DetailedRom): string {
  const states = rom.user_states?.map((s) => s.file_name) ?? [];
  const romName = rom.fs_name_no_ext.trim();
  let stateName = `${romName}.state.auto`;
  if (!states.includes(stateName)) return stateName;
  let i = 1;
  stateName = `${romName}.state1`;
  while (states.includes(stateName)) {
    i++;
    stateName = `${romName}.state${i}`;
  }
  return stateName;
}

function buildSaveName(rom: DetailedRom): string {
  const saves = rom.user_saves?.map((s) => s.file_name) ?? [];
  const romName = rom.fs_name_no_ext.trim();
  let saveName = `${romName}.srm`;
  if (!saves.includes(saveName)) return saveName;
  let i = 2;
  saveName = `${romName} (${i}).srm`;
  while (saves.includes(saveName)) {
    i++;
    saveName = `${romName} (${i}).srm`;
  }
  return saveName;
}

export async function saveState({
  rom,
  state,
  stateFile,
  screenshotFile,
}: {
  rom: DetailedRom;
  state: StateSchema | null;
  stateFile: Uint8Array;
  screenshotFile?: Uint8Array;
}): Promise<StateSchema | null> {
  if (state) {
    const { data } = await stateApi.updateState({
      state: state,
      stateFile: new File([stateFile], state.file_name, {
        type: "application/octet-stream",
      }),
    });
    return data;
  } else {
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
}

export async function saveSave({
  rom,
  save,
  saveFile,
  screenshotFile,
}: {
  rom: DetailedRom;
  save: SaveSchema | null;
  saveFile: Uint8Array;
  screenshotFile?: Uint8Array;
}): Promise<SaveSchema | null> {
  if (save) {
    const { data } = await saveApi.updateSave({
      save: save,
      saveFile: new File([saveFile], save.file_name, {
        type: "application/octet-stream",
      }),
    });
    return data;
  } else {
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
}
