import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import { type DetailedRom } from "@/stores/roms";
import { type SaveSchema } from "@/__generated__";
import { type StateSchema } from "@/__generated__";

function buildStateName(rom: DetailedRom): string {
  const romName = rom.fs_name_no_ext.trim();
  return `${romName} [${new Date().toISOString().replace(/[:.]/g, "-").replace("T", " ").replace("Z", "")}]`;
}

function buildSaveName(rom: DetailedRom): string {
  const romName = rom.fs_name_no_ext.trim();
  return `${romName} [${new Date().toISOString().replace(/[:.]/g, "-").replace("T", " ").replace("Z", "")}]`;
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
          stateFile: new File([stateFile], `${filename}.state`, {
            type: "application/octet-stream",
          }),
          screenshotFile: screenshotFile
            ? new File([screenshotFile], `${filename}.png`, {
                type: "application/octet-stream",
              })
            : undefined,
        },
      ],
    });

    const uploadedState = uploadedStates[0];
    if (uploadedState.status == "fulfilled") {
      if (rom) rom.user_states.unshift(uploadedState.value);
      return uploadedState.value;
    }
  } catch (error) {
    console.error("Failed to upload state", error);
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
      const { data: updatedSave } = await saveApi.updateSave({
        save: save,
        saveFile: new File([saveFile], save.file_name, {
          type: "application/octet-stream",
        }),
        screenshotFile:
          screenshotFile && save.screenshot
            ? new File([screenshotFile], save.screenshot.file_name, {
                type: "application/octet-stream",
              })
            : undefined,
      });

      // Update the save in the rom object
      const index = rom.user_saves.findIndex((s) => s.id === updatedSave.id);
      rom.user_saves[index] = updatedSave;

      return updatedSave;
    } catch (error) {
      console.error("Failed to update save", error);
      return null;
    }
  }

  const filename = buildSaveName(rom);
  try {
    const uploadedSaves = await saveApi.uploadSaves({
      rom: rom,
      emulator: window.EJS_core,
      savesToUpload: [
        {
          saveFile: new File([saveFile], `${filename}.srm`, {
            type: "application/octet-stream",
          }),
          screenshotFile: screenshotFile
            ? new File([screenshotFile], `${filename}.png`, {
                type: "application/octet-stream",
              })
            : undefined,
        },
      ],
    });

    const uploadedSave = uploadedSaves[0];
    if (uploadedSave.status == "fulfilled") {
      if (rom) rom.user_saves.unshift(uploadedSave.value);
      return uploadedSave.value;
    }
  } catch (error) {
    console.error("Failed to upload save", error);
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

export function createQuickLoadButton(): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "presentation");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("viewBox", "2 2 20 20");
  svg.innerHTML =
    '<path d="M12,7L17,12H14V16H10V12H7L12,7M19,21H5A2,2 0 0,1 3,19V5A2,2 0 0,1 5,3H19A2,2 0 0,1 21,5V19A2,2 0 0,1 19,21M19,19V5H5V19H19Z"></path>';
  const text = document.createElement("span");
  text.classList.add("ejs_menu_text");
  text.innerText = "Load Latest State";
  button.classList.add("ejs_menu_button");
  button.appendChild(svg);
  button.appendChild(text);

  const ejsMenuBar = document.querySelector("#game .ejs_menu_bar");
  const loadStateBtn = ejsMenuBar?.querySelector(
    ".ejs_menu_button:nth-child(5)",
  );
  if (ejsMenuBar && loadStateBtn) {
    ejsMenuBar.insertBefore(button, loadStateBtn);
  }

  return button;
}

export function createSaveQuitButton(): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "presentation");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("viewBox", "2 2 20 20");
  svg.innerHTML =
    '<path d="M17,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H11.81C11.42,20.34 11.17,19.6 11.07,18.84C9.5,18.31 8.66,16.6 9.2,15.03C9.61,13.83 10.73,13 12,13C12.44,13 12.88,13.1 13.28,13.29C15.57,11.5 18.83,11.59 21,13.54V7L17,3M15,9H5V5H15V9M13,17H17V14L22,18.5L17,23V20H13V17"></path>';
  const text = document.createElement("span");
  text.classList.add("ejs_menu_text", "ejs_menu_text_right");
  text.innerText = "Save & Quit";
  button.classList.add("ejs_menu_button");
  button.appendChild(svg);
  button.appendChild(text);

  const ejsMenuBar = document.querySelector("#game .ejs_menu_bar");
  ejsMenuBar?.appendChild(button);

  return button;
}
