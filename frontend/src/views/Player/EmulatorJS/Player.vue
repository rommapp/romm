<script setup lang="ts">
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import saveApi, { saveApi as api } from "@/services/api/save";
import stateApi from "@/services/api/state";
import type { DetailedRom } from "@/stores/roms";
import {
  areThreadsRequiredForEJSCore,
  getSupportedEJSCores,
  getControlSchemeForPlatform,
} from "@/utils";
import createIndexedDBDiffMonitor, {
  type Change,
} from "@/utils/indexdb_monitor";
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
    EJS_controlScheme: string | null;
    EJS_emulator: any; // eslint-disable-line @typescript-eslint/no-explicit-any
    EJS_GameManager: any; // eslint-disable-line @typescript-eslint/no-explicit-any
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
window.EJS_controlScheme = getControlSchemeForPlatform(
  romRef.value.platform_slug,
);
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

window.EJS_onLoadState = async function () {
  const state = await api.get(
    stateRef.value!.download_path.replace("/api", ""),
    { responseType: "arraybuffer" },
  );
  window.EJS_emulator.gameManager.loadState(state.data);
};

window.EJS_onGameStart = async () => {
  setTimeout(() => {
    if (saveRef.value) window.EJS_onLoadSave();
    if (stateRef.value) window.EJS_onLoadState();
  }, 10);

  const savesMonitor = await createIndexedDBDiffMonitor("/data/saves", 2000);
  const statesMonitor = await createIndexedDBDiffMonitor(
    "EmulatorJS-states",
    2000,
  );

  // Start monitoring
  savesMonitor.start();
  statesMonitor.start();

  savesMonitor.on("change", (changes: Change[]) => {
    changes.forEach((change) => {
      if (!change.key.includes(romRef.value.file_name_no_ext)) return;

      if (saveRef.value) {
        saveApi
          .updateSave({
            save: saveRef.value,
            file: new File(
              [change.newValue.contents],
              saveRef.value.file_name,
              {
                type: "application/octet-stream",
              },
            ),
          })
          .then(({ data }) => {
            saveRef.value = data;
          })
          .catch();
      } else {
        const filename =
          change.key.split("/").pop() ?? `${romRef.value.file_name_no_ext}.sav`;

        saveApi
          .uploadSaves({
            rom: romRef.value,
            emulator: window.EJS_core,
            saves: [
              new File([change.newValue.contents], filename, {
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
          })
          .catch();
      }
    });
  });

  statesMonitor.on("change", (changes: Change[]) => {
    console.log("State changes detected:", changes);
  });
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
