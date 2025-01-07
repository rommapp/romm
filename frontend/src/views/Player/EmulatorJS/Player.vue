<script setup lang="ts">
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import saveApi, { saveApi as api } from "@/services/api/save";
import screenshotApi from "@/services/api/screenshot";
import stateApi from "@/services/api/state";
import type { DetailedRom } from "@/stores/roms";
import { areThreadsRequiredForEJSCore, getSupportedEJSCores } from "@/utils";
import { onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps<{
  rom: DetailedRom;
  save: SaveSchema | null;
  state: StateSchema | null;
  bios: FirmwareSchema | null;
  core: string | null;
}>();
const romRef = ref<DetailedRom>(props.rom);
const saveRef = ref<SaveSchema | null>(props.save);
const stateRef = ref<StateSchema | null>(props.state);

// Declare global variables for EmulatorJS
declare global {
  interface Window {
    EJS_core: string;
    EJS_biosUrl: string;
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
    EJS_alignStartButton: "top" | "center" | "bottom";
    EJS_startOnLoaded: boolean;
    EJS_fullscreenOnLoaded: boolean;
    EJS_threads: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    EJS_emulator: any;
    EJS_onGameStart: () => void;
    EJS_onSaveState: (args: { screenshot: File; state: File }) => void;
    EJS_onLoadState: () => void;
    EJS_onSaveSave: (args: { screenshot: File; save: File }) => void;
    EJS_onLoadSave: () => void;
  }
}

const supportedCores = getSupportedEJSCores(romRef.value.platform_slug);
window.EJS_core =
  supportedCores.find((core) => core === props.core) ?? supportedCores[0];
window.EJS_threads = areThreadsRequiredForEJSCore(window.EJS_core);
window.EJS_gameID = romRef.value.id;
window.EJS_gameUrl = `/api/roms/${romRef.value.id}/content/${romRef.value.file_name}`;
window.EJS_biosUrl = props.bios
  ? `/api/firmware/${props.bios.id}/content/${props.bios.file_name}`
  : "";
window.EJS_player = "#game";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_backgroundImage = "/assets/emulatorjs/loading_black.png";
window.EJS_defaultOptions = {
  "save-state-location": "browser",
  rewindEnabled: "enabled",
};
if (romRef.value.name) window.EJS_gameName = romRef.value.name;

onBeforeUnmount(() => {
  window.location.reload();
});

onMounted(() => {
  if (props.save) {
    localStorage.setItem(
      `player:${props.rom.id}:save_id`,
      props.save.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.id}:save_id`);
  }

  if (props.state) {
    localStorage.setItem(
      `player:${props.rom.id}:state_id`,
      props.state.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.id}:state_id`);
  }

  if (props.bios) {
    localStorage.setItem(
      `player:${props.rom.platform_slug}:bios_id`,
      props.bios.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.platform_slug}:bios_id`);
  }

  if (props.core) {
    localStorage.setItem(`player:${props.rom.platform_slug}:core`, props.core);
  } else {
    localStorage.removeItem(`player:${props.rom.platform_slug}:core`);
  }
});

function buildStateName(): string {
  const states = romRef.value.user_states?.map((s) => s.file_name) ?? [];
  const romName = romRef.value.file_name_no_ext.trim();
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
  const saves = romRef.value.user_saves?.map((s) => s.file_name) ?? [];
  const romName = romRef.value.file_name_no_ext.trim();
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
      { responseType: "arraybuffer" },
    );
    if (data) {
      window.EJS_emulator.displayMessage("LOADED FROM ROMM");
      return new Uint8Array(data);
    }
  }

  if (window.EJS_emulator.saveInBrowserSupported()) {
    const data = await window.EJS_emulator.storage.states.get(
      window.EJS_emulator.getBaseFileName() + ".state",
    );
    if (data) {
      window.EJS_emulator.displayMessage("LOADED FROM BROWSER");
      return data;
    }
  }

  const file = await window.EJS_emulator.selectFile();
  return new Uint8Array(await file.arrayBuffer());
}

function downloadFallback(data: BlobPart, name: string) {
  const url = window.URL.createObjectURL(
    new Blob([data], { type: "application/octet-stream" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  window.URL.revokeObjectURL(url);
}

window.EJS_onLoadState = async function () {
  const state = await fetchState();
  window.EJS_emulator.gameManager.loadState(state);
};

window.EJS_onSaveState = function ({
  state,
  screenshot,
}: {
  screenshot: BlobPart;
  state: BlobPart;
}) {
  if (window.EJS_emulator.saveInBrowserSupported()) {
    window.EJS_emulator.storage.states.put(
      window.EJS_emulator.getBaseFileName() + ".state",
      state,
    );
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
        window.EJS_emulator.displayMessage("SAVED TO ROMM");

        if (stateRef.value.screenshot) {
          screenshotApi
            .updateScreenshot({
              screenshot: stateRef.value.screenshot,
              file: new File(
                [screenshot],
                stateRef.value.screenshot.file_name,
                {
                  type: "application/octet-stream",
                },
              ),
            })
            .then(({ data }) => {
              if (stateRef.value) stateRef.value.screenshot = data;
            })
            .catch((e) => console.log(e));
        } else {
          screenshotApi
            .uploadScreenshots({
              rom: romRef.value,
              screenshots: [
                new File([screenshot], `${buildStateName()}.png`, {
                  type: "application/octet-stream",
                }),
              ],
            })
            .then(({ data }) => {
              if (stateRef.value)
                stateRef.value.screenshot = data.screenshots[0];
              romRef.value.user_screenshots = data.screenshots;
              romRef.value.merged_screenshots = data.merged_screenshots;
            })
            .catch((e) => console.log(e));
        }
      })
      .catch(() => {
        if (window.EJS_emulator.saveInBrowserSupported()) {
          window.EJS_emulator.displayMessage("SAVED TO BROWSER");
        } else {
          downloadFallback(state, stateRef.value?.file_name ?? "state");
        }
      });
  } else if (romRef.value) {
    stateApi
      .uploadStates({
        rom: romRef.value,
        emulator: window.EJS_core,
        states: [
          new File([state], buildStateName(), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allStates = data.states.sort(
          (a: StateSchema, b: StateSchema) => a.id - b.id,
        );
        if (romRef.value) romRef.value.user_states = allStates;
        stateRef.value = allStates.pop() ?? null;
        window.EJS_emulator.displayMessage("SAVED TO ROMM");

        screenshotApi
          .uploadScreenshots({
            rom: romRef.value,
            screenshots: [
              new File([screenshot], `${buildStateName()}.png`, {
                type: "application/octet-stream",
              }),
            ],
          })
          .then(({ data }) => {
            romRef.value.user_screenshots = data.screenshots;
            romRef.value.merged_screenshots = data.merged_screenshots;
          })
          .catch((e) => console.log(e));
      })
      .catch(() => {
        if (window.EJS_emulator.saveInBrowserSupported()) {
          window.EJS_emulator.displayMessage("SAVED TO BROWSER");
        } else {
          downloadFallback(state, buildStateName());
        }
      });
  }
};

async function fetchSave(): Promise<Uint8Array> {
  if (saveRef.value) {
    const { data } = await api.get(
      saveRef.value.download_path.replace("/api", ""),
      { responseType: "arraybuffer" },
    );
    if (data) return new Uint8Array(data);
  }

  const file = await window.EJS_emulator.selectFile();
  return new Uint8Array(await file.arrayBuffer());
}

window.EJS_onLoadSave = async function () {
  const sav = await fetchSave();
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
  FS.writeFile(path, sav);
  window.EJS_emulator.gameManager.loadSaveFiles();
};

window.EJS_onSaveSave = function ({
  save,
  screenshot,
}: {
  save: BlobPart;
  screenshot: BlobPart;
}) {
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

        if (saveRef.value.screenshot) {
          screenshotApi
            .updateScreenshot({
              screenshot: saveRef.value.screenshot,
              file: new File([screenshot], saveRef.value.screenshot.file_name, {
                type: "application/octet-stream",
              }),
            })
            .then(({ data }) => {
              if (saveRef.value) saveRef.value.screenshot = data;
            })
            .catch((e) => console.log(e));
        } else {
          screenshotApi
            .uploadScreenshots({
              rom: romRef.value,
              screenshots: [
                new File([screenshot], `${buildSaveName()}.png`, {
                  type: "application/octet-stream",
                }),
              ],
            })
            .then(({ data }) => {
              if (saveRef.value) saveRef.value.screenshot = data.screenshots[0];
              romRef.value.user_screenshots = data.screenshots;
              romRef.value.merged_screenshots = data.merged_screenshots;
            })
            .catch((e) => console.log(e));
        }
      })
      .catch(() => {
        downloadFallback(save, saveRef.value?.file_name ?? "save");
      });
  } else if (romRef.value) {
    saveApi
      .uploadSaves({
        rom: romRef.value,
        emulator: window.EJS_core,
        saves: [
          new File([save], buildSaveName(), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allSaves = data.saves.sort(
          (a: SaveSchema, b: SaveSchema) => a.id - b.id,
        );
        if (romRef.value) romRef.value.user_saves = allSaves;
        saveRef.value = allSaves.pop() ?? null;

        screenshotApi
          .uploadScreenshots({
            rom: romRef.value,
            screenshots: [
              new File([screenshot], `${buildSaveName()}.png`, {
                type: "application/octet-stream",
              }),
            ],
          })
          .then(({ data }) => {
            romRef.value.user_screenshots = data.screenshots;
            romRef.value.merged_screenshots = data.merged_screenshots;
          })
          .catch((e) => console.log(e));
      })
      .catch(() => {
        downloadFallback(save, buildSaveName());
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
  <div id="game" />
</template>

<style scoped>
#game {
  max-height: 100dvh;
}
</style>

<style>
#game .ejs_cheat_code {
  background-color: white;
}
</style>

<!-- Other config options: https://emulatorjs.org/docs/options -->

<!-- window.EJS_biosUrl; -->
<!-- window.EJS_VirtualGamepadSettings; -->
<!-- window.EJS_cheats; -->
<!-- window.EJS_gamePatchUrl; -->
<!-- window.EJS_gameParentUrl; -->
<!-- window.EJS_netplayServer; -->
