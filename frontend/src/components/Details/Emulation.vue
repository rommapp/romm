<script setup lang="ts">
import { isNull } from "lodash";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import rom from "@/services/api/rom";
import type { UserRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import Player from "@/views/Play/Player.vue";
import { ref } from "vue";
import type { Platform } from "@/stores/platforms";

const props = defineProps<{ rom: UserRom; platform: Platform }>();
const biosRef = ref<FirmwareSchema | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const gameRunning = ref(false);

const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;

function onPlay() {
  window.EJS_fullscreenOnLoaded = fullScreenOnPlay.value;
  document.body.appendChild(script);
  gameRunning.value = true;
}

function onFullScreenChange() {
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}
</script>

<template>
  <v-row v-if="rom && !gameRunning" no-gutters class="align-center">
    <v-col cols="5" class="text-truncate mx-1">
      <v-select
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        label="BIOS"
        v-model="biosRef"
        :items="
          props.platform.firmware?.map((f) => ({
            title: f.file_name,
            value: f,
          })) ?? []
        "
      />
      <v-select
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        label="Save"
        v-model="saveRef"
        :items="
          props.rom.user_saves?.map((s) => ({
            title: s.file_name,
            subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
            value: s,
          })) ?? []
        "
      />
      <v-select
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        label="State"
        v-model="stateRef"
        :items="
          props.rom.user_states?.map((s) => ({
            title: s.file_name,
            subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
            value: s,
          })) ?? []
        "
      />
      <!-- <v-select
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        disabled
        label="Patch"
        :items="[
          'Advance Wars Balance (AW1) by Kartal',
          'War Room Sturm (AW1) by Kartal',
        ]"
      /> -->
      <v-checkbox
        hide-details
        v-model="fullScreenOnPlay"
        @change="onFullScreenChange"
        color="romm-accent-1"
        label="Full screen"
      />
    </v-col>
    <v-col cols="6" class="mx-1">
      <v-img
        class="bg-black"
        height="160"
        :src="
          stateRef?.screenshot?.download_path ??
          props.rom.merged_screenshots[0] ??
          `/assets/emulatorjs/loading_black.png`
        "
      />
    </v-col>
  </v-row>

  <v-row no-gutters class="align-center mt-6" v-if="!gameRunning">
    <v-col cols="5">
      <v-btn
        block
        density="compact"
        class="text-romm-accent-1"
        variant="outlined"
        size="x-large"
        @click="onPlay()"
      >
        <v-icon class="mr-2">mdi-play</v-icon>Play
      </v-btn>
    </v-col>
    <v-spacer />
    <v-col cols="5">
      <img width="150" src="/assets/emulatorjs/powered_by_emulatorjs.png" />
    </v-col>
  </v-row>

  <v-row no-gutters>
    <v-col v-if="gameRunning" cols="12" rounded id="game-wrapper">
      <player :rom="props.rom" :state="stateRef" :save="saveRef" :bios="biosRef" />
    </v-col>
  </v-row>
</template>

<style>
#game-wrapper {
  aspect-ratio: 16 / 9;
}
</style>
