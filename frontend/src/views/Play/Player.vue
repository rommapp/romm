<script setup lang="ts">
import { ref } from "vue";
import stateApi from "@/services/api/state";
import saveApi, { saveApi as api } from "@/services/api/save";
import type { Rom } from "@/stores/roms";
import type { SaveSchema, StateSchema } from "@/__generated__";

const props = defineProps<{
  rom: Rom;
  save: SaveSchema | null;
  state: StateSchema | null;
}>();
const saveRef = ref<SaveSchema | null>(props.save);
const stateRef = ref<StateSchema | null>(props.state);

// Uses a different regex for jaavscript
const EXTENSION_REGEX = new RegExp("\.(([a-z]+\.)*)$");

// Declare global variables for EmulatorJS
declare global {
  interface Window {
    EJS_core: string;
    EJS_player: string;
    EJS_pathtodata: string;
    EJS_color: string;
    EJS_defaultOptions: object;
    EJS_gameID: number;
    EJS_gameName: string;
    EJS_backgroundImage: string;
    EJS_gameUrl: string;
    EJS_loadStateURL: string | null;
    EJS_cheats: string;
    EJS_gamePatchUrl: string;
    EJS_netplayServer: string;
    EJS_alignStartButton: string;
    EJS_startOnLoaded: boolean;
    EJS_fullscreenOnLoaded: boolean;
    EJS_emulator: any;
    EJS_onGameStart: () => void;
    EJS_onSaveState: (args: { screenshot: File; state: File }) => void;
    EJS_onLoadState: () => void;
    EJS_onSaveSave: (args: { screenshot: File; save: File }) => void;
    EJS_onLoadSave: () => void;
  }
}

window.EJS_core = props.rom.platform_slug;
window.EJS_gameID = props.rom.id;
window.EJS_backgroundImage =
  props.rom.url_screenshots[0] ||
  `/assets/romm/resources/${props.rom.path_cover_l}`;
window.EJS_gameUrl = props.rom.download_path;
window.EJS_player = "#game";
window.EJS_pathtodata = "/assets/emulatorjs/";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_fullscreenOnLoaded = false;
window.EJS_defaultOptions = { "save-state-location": "browser" };
if (props.rom.name) window.EJS_gameName = props.rom.name;

function buildStateName(): string {
  const states = props.rom.states.map((s) => s.file_name);
  const romName = props.rom.file_name.replace(EXTENSION_REGEX, "").trim();
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

function buildSaveName(): string {
  const saves = props.rom.saves.map((s) => s.file_name);
  const romName = props.rom.file_name.replace(EXTENSION_REGEX, "").trim();
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

async function fetchState(): Promise<Uint8Array> {
  if (stateRef.value) {
    const { data } = await api.get(
      stateRef.value.download_path.replace("/api", ""),
      { responseType: "arraybuffer" }
    );
    return new Uint8Array(data);
  } else if (window.EJS_emulator.saveInBrowserSupported()) {
    const data = await window.EJS_emulator.storage.states.get(
      window.EJS_emulator.getBaseFileName() + ".state"
    );
    return data;
  }
  return new Uint8Array();
}

window.EJS_onLoadState = async function () {
  const stat = await fetchState();
  window.EJS_emulator.gameManager.loadState(stat);
  window.EJS_emulator.displayMessage("LOADED FROM ROMM");
};

window.EJS_onSaveState = function ({
  state,
}: {
  screenshot: File;
  state: File;
}) {
  if (window.EJS_emulator.saveInBrowserSupported()) {
    window.EJS_emulator.storage.states.put(
      window.EJS_emulator.getBaseFileName() + ".state",
      state
    );
    window.EJS_emulator.displayMessage("SAVED TO ROMM");
  }
  if (stateRef.value) {
    stateApi
      .updateState({
        state: stateRef.value,
        file: new File([state], stateRef.value.file_name, {
          type: "application/octet-stream",
        }),
      })
      .then(({ data }) => {
        stateRef.value = data;
      });
  } else if (props.rom) {
    stateApi
      .uploadStates({
        rom: props.rom,
        states: [
          new File([state], buildStateName(), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allStates = data.states.sort(
          (a: StateSchema, b: StateSchema) => a.id - b.id
        );
        if (props.rom) props.rom.states = allStates;
        stateRef.value = allStates.pop() ?? null;
      });
  }
};

async function fetchSave(): Promise<Uint8Array> {
  if (saveRef.value) {
    const { data } = await api.get(
      saveRef.value.download_path.replace("/api", ""),
      { responseType: "arraybuffer" }
    );
    return new Uint8Array(data);
  }

  const file = await window.EJS_emulator.selectFile();
  return new Uint8Array(await file.arrayBuffer());
}

window.EJS_onLoadSave = async function () {
  const sav = await fetchSave();
  const FS = window.EJS_emulator.Module.FS;
  const path = window.EJS_emulator.gameManager.getSaveFilePath();
  const paths = path.split("/");
  let cp = "";
  for (let i = 0; i < paths.length - 1; i++) {
    if (paths[i] === "") continue;
    cp += "/" + paths[i];
    if (!FS.analyzePath(cp).exists) FS.mkdir(cp);
  }
  if (FS.analyzePath(path).exists) FS.unlink(path);
  FS.writeFile(path, sav);
  window.EJS_emulator.gameManager.loadSaveFiles();
};

window.EJS_onSaveSave = function ({ save }: { screenshot: File; save: File }) {
  if (saveRef.value) {
    saveApi
      .updateSave({
        save: saveRef.value,
        file: new File([save], saveRef.value.file_name, {
          type: "application/octet-stream",
        }),
      })
      .then(({ data }) => {
        saveRef.value = data;
      });
  } else if (props.rom) {
    saveApi
      .uploadSaves({
        rom: props.rom,
        saves: [
          new File([save], buildSaveName(), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allSaves = data.saves.sort(
          (a: SaveSchema, b: SaveSchema) => a.id - b.id
        );
        if (props.rom) props.rom.saves = allSaves;
        saveRef.value = allSaves.pop() ?? null;
      });
  }
};

window.EJS_onGameStart = async () => {
  saveRef.value = props.save;
  stateRef.value = props.state;

  setTimeout(() => {
    if (stateRef.value) window.EJS_onLoadState();
    if (saveRef.value) window.EJS_onLoadSave();
  }, 10);
};
</script>

<template>
  <div id="game"></div>
</template>

<style>
div.ejs_game {
  background-color: #191d22;
}
</style>

<!-- Other config options: https://emulatorjs.org/docs/Options.html -->

<!-- config.biosUrl = window.EJS_biosUrl; -->
<!-- config.VirtualGamepadSettings = window.EJS_VirtualGamepadSettings; -->
<!-- config.buttonOpts = window.EJS_Buttons; -->
<!-- config.volume = window.EJS_volume; -->
<!-- config.defaultControllers = window.EJS_defaultControls; -->
<!-- config.cheats = window.EJS_cheats; -->
<!-- config.defaultOptions = window.EJS_defaultOptions; -->
<!-- config.gamePatchUrl = window.EJS_gamePatchUrl; -->
<!-- config.gameParentUrl = window.EJS_gameParentUrl; -->
<!-- config.netplayUrl = window.EJS_netplayServer; -->
<!-- config.threads = window.EJS_threads; -->
