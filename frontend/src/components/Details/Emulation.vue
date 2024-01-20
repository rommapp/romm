<script setup lang="ts">
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { Rom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import Player from "@/views/Play/Player.vue";
import { ref, onMounted } from "vue";
import { useDisplay } from "vuetify";

const props = defineProps<{ rom: Rom }>();
const saveRef = ref<SaveSchema | null>(null);
const stateRef = ref<StateSchema | null>(null);
const fullScreenOnPlay = ref(true);
const gameRunning = ref(false);
const { smAndDown, mdAndUp } = useDisplay();

const script = document.createElement("script");
script.src = "/assets/emulatorjs/loader.js";
script.async = true;

function onPlay() {
  // let backgroundImage = `/assets/romm/resources/${props.rom.platform_slug}/${props.rom.name}/screenshots/states/${stateRef.value?.file_name}.jpg`
  let backgroundImage = `/assets/romm/resources/${props.rom.path_cover_l}`;
  window.EJS_backgroundImage = backgroundImage
  window.EJS_fullscreenOnLoaded = fullScreenOnPlay.value;
  document.body.appendChild(script);
  gameRunning.value = true;
}

onMounted(() => {
  const wrapper = document.getElementById("game-wrapper");
  if (wrapper) wrapper.style.backgroundImage = `url(${window.EJS_backgroundImage})`;
});
</script>

<template>
  <v-row v-if="rom && !gameRunning" no-gutters class="align-center">
    <v-col cols="5" class="text-truncate mx-1">
      <!-- <v-select
        density="compact"
        class="my-2"
        hide-details
        variant="outlined"
        clearable
        disabled
        label="BIOS"
        :items="['gba-bios.zip']"
      /> -->
      <v-select
        density="compact"
        class="my-2"
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
        density="compact"
        class="my-2"
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
      <v-switch
        hide-details
        v-model="fullScreenOnPlay"
        color="romm-accent-1"
        label="Full screen"
      />
    </v-col>
    <v-col cols="6" class="mx-1">
      <v-img
        class="bg-black"
        height="160"
        :src="`/assets/romm/resources/${props.rom.platform_slug}/${props.rom.name}/screenshots/states/${stateRef?.file_name}.jpg`"
      />
    </v-col>
  </v-row>

  <v-row no-gutters class="align-center mt-6" v-if="!gameRunning">
    <v-col cols="12" lg="7" xl="7">
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
    <v-col cols="12" lg="5" xl="5">
      <img
        :class="{ 'mt-6': smAndDown, 'ml-7': mdAndUp }"
        width="150"
        src="/assets/powered_by_emulatorjs.png"
      />
    </v-col>
  </v-row>

  <v-row no-gutters>
    <v-col v-if="gameRunning" cols="12" rounded id="game-wrapper">
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
