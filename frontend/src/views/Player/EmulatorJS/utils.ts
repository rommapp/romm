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
  file,
}: {
  rom: DetailedRom;
  state: StateSchema | null;
  file: File;
}): Promise<StateSchema | null> {
  if (state) {
    const { data } = await stateApi.updateState({
      state: state,
      file: new File([file], state.file_name, {
        type: "application/octet-stream",
      }),
    });
    return data;
  } else {
    const { data } = await stateApi.uploadStates({
      rom: rom,
      emulator: window.EJS_core,
      states: [
        new File([file], buildStateName(rom), {
          type: "application/octet-stream",
        }),
      ],
    });

    const allStates = data.states.sort(
      (a: StateSchema, b: StateSchema) => a.id - b.id,
    );
    if (rom) rom.user_states = allStates;
    return allStates.pop() ?? null;
  }
}

export async function saveSave({
  rom,
  save,
  file,
}: {
  rom: DetailedRom;
  save: SaveSchema | null;
  file: File;
}): Promise<SaveSchema | null> {
  if (save) {
    const { data } = await saveApi.updateSave({
      save: save,
      file: new File([file], save.file_name, {
        type: "application/octet-stream",
      }),
    });
    return data;
  } else {
    const { data } = await saveApi.uploadSaves({
      rom: rom,
      emulator: window.EJS_core,
      saves: [
        new File([file], buildSaveName(rom), {
          type: "application/octet-stream",
        }),
      ],
    });
    const allSaves = data.saves.sort(
      (a: SaveSchema, b: SaveSchema) => a.id - b.id,
    );
    if (rom) rom.user_saves = allSaves;
    return allSaves.pop() ?? null;
  }
}
