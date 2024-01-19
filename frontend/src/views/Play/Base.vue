<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import romApi from "@/services/api/rom";
import stateApi from "@/services/api/state";
import saveApi, { saveApi as api } from "@/services/api/save";
import type { Rom } from "@/stores/roms";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes } from "@/utils";

const route = useRoute();
const rom = ref<Rom | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const gameRunning = ref(false);
const gameWindow = ref(9);

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

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;
window.EJS_player = "#game";
window.EJS_pathtodata = "/assets/emulatorjs/";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_fullscreenOnLoaded = false;
window.EJS_defaultOptions = {
  "save-state-location": "browser",
};

function buildStateName(rom: Rom): string {
  const states = rom.states.map((s) => s.file_name);
  const romName = rom.file_name.replace(EXTENSION_REGEX, "").trim();
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

function buildSaveName(rom: Rom): string {
  const saves = rom.saves.map((s) => s.file_name);
  const romName = rom.file_name.replace(EXTENSION_REGEX, "").trim();
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
    window.EJS_emulator.displayMessage(
      window.EJS_emulator.localization("SAVE SAVED TO BROWSER")
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
      });
  } else if (rom.value) {
    stateApi
      .uploadStates({
        rom: rom.value,
        states: [
          new File([state], buildStateName(rom.value), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allStates = data.states.sort((a: StateSchema, b: StateSchema) => a.id - b.id);
        if (rom.value) rom.value.states = allStates;
        stateRef.value = allStates.pop() ?? null;
      });
  }
};

async function getSave(): Promise<Uint8Array> {
  if (saveRef.value) {
    const { data } = await api.get(
      saveRef.value.download_path.replace("/api", "")
    );
    var enc = new TextEncoder();
    return enc.encode(data);
  } else {
    const file = await window.EJS_emulator.selectFile();
    return new Uint8Array(await file.arrayBuffer());
  }
}

window.EJS_onLoadSave = async function () {
  const sav = await getSave();
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
  } else if (rom.value) {
    saveApi
      .uploadSaves({
        rom: rom.value,
        saves: [
          new File([save], buildSaveName(rom.value), {
            type: "application/octet-stream",
          }),
        ],
      })
      .then(({ data }) => {
        const allSaves = data.saves.sort((a: SaveSchema, b: SaveSchema) => a.id - b.id);
        if (rom.value) rom.value.saves = allSaves;
        saveRef.value = allSaves.pop() ?? null;
      });
  }
};

window.EJS_onGameStart = async () => {
  setTimeout(() => {
    if (stateRef.value) {
      window.EJS_onLoadSave();
      window.EJS_emulator.gameManager.restart();
    }
  }, 1000);
  gameRunning.value = true;
};

onMounted(() => {
  romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
      window.EJS_core = rom.value.platform_slug;
      window.EJS_gameID = rom.value.id;
      window.EJS_backgroundImage = `/assets/romm/resources/${rom.value.path_cover_l}`;
      window.EJS_gameUrl = rom.value.download_path;
      if (rom.value.name) window.EJS_gameName = rom.value.name;
    })
    .catch((error) => {
      console.log(error);
    });
});

function onPlay() {
  gameWindow.value = 12;
  gameRunning.value = true;
  window.EJS_loadStateURL = stateRef.value?.download_path ?? null;
  document.body.appendChild(script);
}
</script>

<template>
  <v-container class="h-100">
    <v-row class="h-100">
      <v-col v-if="rom && !gameRunning" class="v-col-3">
        <v-select
          clearable
          label="Save"
          v-model="saveRef"
          :items="
            rom.saves.map((s) => ({
              title: s.file_name,
              subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
              value: s,
            }))
          "
        />
        <v-select
          clearable
          label="State"
          v-model="stateRef"
          :items="
            rom.states.map((s) => ({
              title: s.file_name,
              subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
              value: s,
            }))
          "
        />
        <v-select clearable disabled label="BIOS" :items="['gba-bios.zip']" />
        <v-select
          clearable
          disabled
          label="Patch"
          :items="[
            'Advance Wars Balance (AW1) by Kartal',
            'War Room Sturm (AW1) by Kartal',
          ]"
        />
        <v-btn rounded="0" size="x-large" @click="onPlay()"> Play </v-btn>
      </v-col>
      <v-col>
        <v-sheet rounded id="game-wrapper">
          <div id="game"></div>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<style>
div.ejs_game {
  background-color: #191d22;
}
#game-wrapper {
  aspect-ratio: 16 / 9;
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
