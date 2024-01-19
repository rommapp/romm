<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import apiRom from "@/services/apiRom";
import type { Rom } from "@/stores/roms";

const route = useRoute();
const rom = ref<Rom | null>(null);
const gameRunning = ref(false);

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;
window.EJS_player = "#game";
window.EJS_pathtodata = "/assets/emulatorjs/";
window.EJS_color = "#A453FF";
window.EJS_defaultOptions = {
  "save-state-location": "browser",
};
// window.EJS_onSaveState = function ({ screenshot, state }) {
//   // Save to backend as .state file
// };
// window.EJS_onLoadState = function () {
//   // Load the latest state from file
// };
window.EJS_onGameStart = () => {
  gameRunning.value = true;
};
// Other config options to investigate:
// config.loadState = window.EJS_loadStateURL; // https://emulatorjs.org/docs/Options.html#ejs-loadstateurl
// config.cheats = window.EJS_cheats; // https://emulatorjs.org/docs/Options.html#ejs-cheats
// config.gamePatchUrl = window.EJS_gamePatchUrl; // https://emulatorjs.org/docs/Options.html#ejs-gamepatchurl
// config.netplayUrl = window.EJS_netplayServer; // https://emulatorjs.org/docs4devs/Netplay.html
onMounted(() => {
  apiRom.getRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
      window.EJS_core = rom.value.platform_slug;
      window.EJS_gameID = rom.value.id;
      window.EJS_gameName = rom.value.name;
      window.EJS_backgroundImage = `/assets/romm/resources/${rom.value.path_cover_l}`;
      window.EJS_gameUrl = rom.value.download_path;
      document.body.appendChild(script);
    })
    .catch((error) => {
      console.log(error);
    });
});
</script>

<template>
  <v-container class="h-100">
    <v-row class="h-100">
      <v-col v-if="!gameRunning" class="v-col-3">
        <v-select
          clearable
          label="Save"
          :items="['Advance Wars.srm']"
        />
        <v-select
          clearable
          label="State"

          :items="['Advance Wars.state', 'Advance Wars (2).state']"
        />
        <v-select
          clearable
          label="BIOS"

          :items="['gba-bios.zip']"
        />
        <v-select
          clearable
          label="Patch"

          :items="[
            'Advance Wars Balance (AW1) by Kartal',
            'War Room Sturm (AW1) by Kartal',
          ]"
        />
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
  background-color: #191D22;
}
#game-wrapper {
  aspect-ratio: 16 / 9;
}
</style>
