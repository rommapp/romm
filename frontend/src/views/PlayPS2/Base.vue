<script setup lang="ts">
import { isNull } from "lodash";
import { onMounted, ref, nextTick } from "vue";
import { useRoute } from "vue-router";

import RAvatar from "@/components/common/Game/RAvatar.vue";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";

import DiskImageDevice from "./diskImageDevice";

const MODULE_OVERRIDES = {
  locateFile: function (path: string) {
    return window.location.origin + "/assets/playps2/" + path;
  },
  mainScriptUrlOrBlob: window.location.origin + "/assets/playps2/playps2.js",
};

const route = useRoute();
const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

function onPlay() {
  gameRunning.value = true;

  nextTick(async () => {
    if (!rom.value) return;

    const { default: PlayPS2 } = await import(
      /* @vite-ignore */
      window.location.origin + "/assets/playps2/playps2.js"
    );
    const PlayModule = await PlayPS2(MODULE_OVERRIDES);
    PlayModule.FS.mkdir("/work");
    PlayModule.discImageDevice = new DiskImageDevice(PlayModule);
    PlayModule.ccall("initVm", "", [], []);

    const url = `/api/roms/${rom.value.id}/content/${rom.value.file_name}`;
    const response = await fetch(url);
    if (!response.ok) {
      console.error("Network response was not ok");
      return null;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      console.error("Response body is not readable");
      return null;
    }

    if (rom.value.file_extension === ".elf") {
      const stream = PlayModule.FS.open(rom.value.file_name, "w+");
      let offset = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        PlayModule.FS.write(stream, value, offset, value.length, offset);
        offset += value.length;
      }
      PlayModule.FS.close(stream);
      URL.revokeObjectURL(url);
      PlayModule.bootElf(rom.value.file_name);
    } else {
      const chunks: Uint8Array[] = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }

      const file = new Blob(chunks, { type: "application/octet-stream" });
      PlayModule.discImageDevice.setFile(file);
      PlayModule.bootDiscImage(rom.value.file_name);
    }
  });
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;
});
</script>

<template>
  <v-row v-if="rom" class="align-center justify-center scroll" no-gutters>
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      class="bg-secondary"
      rounded
    >
      <canvas id="outputCanvas" tabindex="-1"></canvas>
    </v-col>

    <v-col
      cols="12"
      :sm="!gameRunning ? 10 : 10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row class="px-3 mt-6" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/ruffle/powered_by_ruffle.png"
          />
          <v-divider class="my-4" />
          <v-list-item class="px-2">
            <template #prepend>
              <r-avatar :rom="rom" />
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
        </v-col>
      </v-row>
      <v-row class="px-3 py-3 text-center" no-gutters>
        <v-col>
          <v-divider class="my-4" />
          <v-row class="align-center" no-gutters>
            <v-col>
              <v-btn
                block
                size="large"
                rounded="0"
                @click="onFullScreenChange"
                :disabled="gameRunning"
                :variant="fullScreenOnPlay ? 'flat' : 'outlined'"
                :color="fullScreenOnPlay ? 'romm-accent-1' : ''"
                ><v-icon class="mr-1">{{
                  fullScreenOnPlay
                    ? "mdi-checkbox-outline"
                    : "mdi-checkbox-blank-outline"
                }}</v-icon
                >Full screen</v-btn
              >
            </v-col>
            <v-col
              cols="12"
              :sm="gameRunning ? 12 : 7"
              :xl="gameRunning ? 12 : 9"
            >
              <v-btn
                color="romm-accent-1"
                block
                :disabled="gameRunning"
                rounded="0"
                variant="outlined"
                size="large"
                prepend-icon="mdi-play"
                @click="onPlay()"
                >Play
              </v-btn>
            </v-col>
          </v-row>
          <v-btn
            class="mt-4"
            block
            rounded="0"
            variant="outlined"
            size="large"
            prepend-icon="mdi-refresh"
            @click="$router.go(0)"
            >Reset session
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

<style scoped>
#outputCanvas {
  height: 480px;
  width: 640px;
}
</style>
