<script setup lang="ts">
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import RAvatar from "@/components/common/Game/Avatar.vue";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes, getSupportedCores } from "@/utils";
import Player from "@/views/Play/Player.vue";
import { isNull } from "lodash";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useTheme } from "vuetify";

// Props
const theme = useTheme();
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

// Functions
function onPlay() {
  window.EJS_fullscreenOnLoaded = fullScreenOnPlay.value;
  document.body.appendChild(script);
  gameRunning.value = true;
}

function onFullScreenChange() {
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}

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
</script>

<template>
  <v-row
    v-if="rom"
    class="align-center justify-center scroll"
    no-gutters
  >
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      class="bg-primary"
      rounded
    >
      <player
        :rom="rom"
        :state="stateRef"
        :save="saveRef"
        :bios="biosRef"
        :core="coreRef"
      />
    </v-col>

    <v-col
      cols="12"
      :sm="!gameRunning ? 10 : 10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row class="px-3 py-3" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/emulatorjs/powered_by_emulatorjs.png"
          />
          <v-divider class="my-4" />
          <v-list-item class="px-2">
            <template #prepend>
              <r-avatar
                :src="
                  !rom.igdb_id && !rom.moby_id
                    ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                    : rom.has_cover
                    ? `/assets/romm/resources/${rom.path_cover_s}`
                    : `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
                "
              />
            </template>
            <v-row no-gutters
              ><v-col>{{ rom.name }}</v-col></v-row
            >
            <v-row no-gutters
              ><v-col class="text-romm-accent-1">{{
                rom.file_name
              }}</v-col></v-row
            >
          </v-list-item>
          <v-divider class="my-4" />
          <v-select
            v-if="supportedCores.length > 1"
            v-model="coreRef"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            label="Core"
            :items="
              supportedCores.map((c) => ({
                title: c,
                value: c,
              }))
            "
          />
          <v-select
            v-model="biosRef"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            label="BIOS"
            :items="
              firmwareOptions.map((f) => ({
                title: f.file_name,
                value: f,
              })) ?? []
            "
          />
          <v-select
            v-model="saveRef"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            label="Save"
            :items="
              rom.user_saves?.map((s) => ({
                title: s.file_name,
                subtitle: `${s.emulator} - ${formatBytes(s.file_size_bytes)}`,
                value: s,
              })) ?? []
            "
          />
          <v-select
            v-model="stateRef"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            label="State"
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
            v-model="fullScreenOnPlay"
            hide-details
            color="romm-accent-1"
            label="Full screen"
            @change="onFullScreenChange"
          />
          <v-divider class="my-4" />
          <v-btn
            color="romm-accent-1"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-play"
            @click="onPlay()"
            >Play
          </v-btn>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-arrow-left"
            @click="
              $router.push({
                name: 'rom',
                params: { rom: rom?.id },
              })
            "
            >Back to game details
          </v-btn>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-arrow-left"
            @click="
              $router.push({
                name: 'platform',
                params: { platform: rom?.platform_id },
              })
            "
            >Back to gallery
          </v-btn>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style>
#game-wrapper {
  aspect-ratio: 16 / 9;
}
</style>
