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
  const filename = buildStateName(rom);
  try {
    const uploadedStates = await stateApi.uploadStates({
      rom: rom,
      emulator: window.EJS_core,
      statesToUpload: [
        {
          stateFile: new File([stateFile], filename, {
            type: "application/octet-stream",
          }),
          screenshotFile: screenshotFile
            ? new File([screenshotFile], filename, {
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
  } catch (e) {
    console.error("Failed to upload state", e);
  }

  return null;
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
    try {
      const { data: updateSave } = await saveApi.updateSave({
        save: save,
        saveFile: new File([saveFile], save.file_name, {
          type: "application/octet-stream",
        }),
      });
      return updateSave;
    } catch (e) {
      console.error("Failed to update save", e);
      return null;
    }
  }

  const saveName = buildSaveName(rom);
  try {
    const uploadedSaves = await saveApi.uploadSaves({
      rom: rom,
      emulator: window.EJS_core,
      savesToUpload: [
        {
          saveFile: new File([saveFile], saveName, {
            type: "application/octet-stream",
          }),
          screenshotFile: screenshotFile
            ? new File([screenshotFile], saveName, {
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
  } catch (e) {
    console.error("Failed to upload save", e);
  }

  return null;
}

export function loadEmulatorJSSave(save: Uint8Array) {
  const FS = window.EJS_emulator.gameManager.FS;
  const path = window.EJS_emulator.gameManager.getSaveFilePath();
  const paths = path.split("/");
  let cp = "";
  for (let i = 0; i < paths.length - 1; i++) {
    if (paths[i] === "") continue;
    cp += "/" + paths[i];
    if (!FS.analyzePath(cp).exists) FS.mkdir(cp);
  }
  if (FS.analyzePath(path).exists) FS.unlink(path);
  FS.writeFile(path, save);
  window.EJS_emulator.gameManager.loadSaveFiles();
}

export function loadEmulatorJSState(state: Uint8Array) {
  window.EJS_emulator.gameManager.loadState(state);
}
