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
    '<path d="M19,3H5C3.89,3 3,3.89 3,5V9H5V5H19V19H5V15H3V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3M10.08,15.58L11.5,17L16.5,12L11.5,7L10.08,8.41L12.67,11H3V13H12.67L10.08,15.58Z"></path>';
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
