<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { Rom } from "@/stores/roms";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes } from "@/utils";
import romApi from "@/services/api/rom";
import { useRoute } from "vue-router";
import Player from "@/views/Play/Player.vue";

const route = useRoute();
const rom = ref<Rom | null>(null);
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const gameRunning = ref(false);

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;

onMounted(() => {
  romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
    })
    .catch((error) => {
      console.log(error);
    }).finally(() => {
      const wrapper = document.getElementById("game-wrapper");
      if (wrapper) wrapper.style.backgroundImage = `url(${window.EJS_backgroundImage})`;
    });
});

function onPlay() {
  document.body.appendChild(script);
  gameRunning.value = true;
}
</script>

<template>
  <v-row v-if="rom" no-gutters>
    <v-col v-if="!gameRunning" cols="3" class="px-3">
      <v-img
        class="mx-auto mt-6 mb-5"
        width="250"
        src="/assets/powered_by_emulatorjs.png"
      />
      <!-- <v-select
        class="my-1"
        hide-details
        variant="outlined"
        clearable
        disabled
        label="BIOS"
        :items="['gba-bios.zip']"
      /> -->
      <v-select
        class="my-1"
        hide-details
        variant="outlined"
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
        class="my-1"
        hide-details
        variant="outlined"
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

    <v-col class="my-4 bg-primary" rounded id="game-wrapper">
      <player :rom="rom" :state="stateRef" :save="saveRef" />
    </v-col>
  </v-row>
</template>

<style>
#game-wrapper {
  aspect-ratio: 16 / 9;
  background-size: contain;
  background-position: center;
}
</style>
