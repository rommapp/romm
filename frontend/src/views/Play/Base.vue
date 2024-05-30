<script setup lang="ts">
import { onMounted, ref } from "vue";
import { isNull } from "lodash";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, getSupportedCores } from "@/utils";
import romApi from "@/services/api/rom";
import firmwareApi from "@/services/api/firmware";
import { useRoute } from "vue-router";
import Player from "@/views/Play/Player.vue";
import type { DetailedRom } from "@/stores/roms";

const route = useRoute();
const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);

const biosRef = ref<FirmwareSchema | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const supportedCores = ref<string[]>([]);
const coreRef = ref<string | null>(null);
const gameRunning = ref(false);

const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;
  supportedCores.value = [...getSupportedCores(rom.value.platform_slug)];
  coreRef.value = supportedCores.value[0];

  const firmwareResponse = await firmwareApi.getFirmware({
    platformId: romResponse.data.platform_id,
  });
  firmwareOptions.value = firmwareResponse.data;
});

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
  <v-row v-if="rom" class="h-screen" no-gutters>
    <v-col v-if="!gameRunning" cols="3" class="px-3">
      <v-img
        class="mx-auto mt-6 mb-5"
        width="250"
        src="/assets/emulatorjs/powered_by_emulatorjs.png"
      />
      <v-select
        v-if="supportedCores.length > 1"
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        label="Core"
        v-model="coreRef"
        :items="
          supportedCores.map((c) => ({
            title: c,
            value: c,
          }))
        "
      />
      <v-select
        class="my-1"
        hide-details
        variant="outlined"
        clearable
        label="BIOS"
        v-model="biosRef"
        :items="
          firmwareOptions.map((f) => ({
            title: f.file_name,
            value: f,
          })) ?? []
        "
      />
      <v-select
        class="my-1"
        hide-details
        variant="outlined"
        clearable
        label="Save"
        v-model="saveRef"
        :items="
          rom.user_saves?.map((s) => ({
            title: s.file_name,
            subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
            value: s,
          })) ?? []
        "
      />
      <v-select
        class="my-1"
        hide-details
        variant="outlined"
        clearable
        label="State"
        v-model="stateRef"
        :items="
          rom.user_states?.map((s) => ({
            title: s.file_name,
            subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
            value: s,
          })) ?? []
        "
      />
      <!-- <v-select
        class="my-1"
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
      <v-btn
        class="mt-4"
        block
        rounded="0"
        variant="outlined"
        size="x-large"
        @click="onPlay()"
      >
        <v-icon class="mr-2">mdi-play</v-icon>Play
      </v-btn>
    </v-col>

    <v-col class="bg-primary" rounded id="game-wrapper">
      <player
        :rom="rom"
        :state="stateRef"
        :save="saveRef"
        :bios="biosRef"
        :core="coreRef"
      />
    </v-col>
  </v-row>
</template>

<style>
#game-wrapper {
  aspect-ratio: 16 / 9;
  max-width: 100%;
  max-height: 100%;
}
</style>
