<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import romApi from "@/services/api/rom";
import stateApi from "@/services/api/state";
import type { Rom } from "@/stores/roms";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes } from "@/utils";

const route = useRoute();
const rom = ref<Rom | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const gameRunning = ref(false);

const EXTENSION_REGEX = new RegExp("\.(([a-z]+\.)*)$");

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;
window.EJS_player = "#game";
window.EJS_pathtodata = "/assets/emulatorjs/";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_fullscreenOnLoaded = true;
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
        if (rom.value) rom.value.states = data.states;
        stateRef.value = data.states.pop();
      });
  }
};

window.EJS_onGameStart = () => {
  gameRunning.value = true;
};

onMounted(() => {
  romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
      window.EJS_core = rom.value.platform_slug;
      window.EJS_gameID = rom.value.id;
      window.EJS_gameName = rom.value.name;
      window.EJS_backgroundImage = `/assets/romm/resources/${rom.value.path_cover_l}`;
      window.EJS_gameUrl = rom.value.download_path;
    })
    .catch((error) => {
      console.log(error);
    });
});

function onPlay() {
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
          disabled
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
