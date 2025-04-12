<script setup lang="ts">
import RomListItem from "@/components/common/Game/ListItem.vue";
import DosWasmX from "@/views/Player/DosBox/Dosbox.vue";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import { getDownloadLink } from "@/utils";
import { ROUTES } from "@/plugins/router";
import { isNull } from "lodash";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import storeDownload from "@/stores/download.ts";

// Props
const { t } = useI18n();
const route = useRoute();
const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");
const downloadStore = storeDownload();
const downloadLink = ref("");

function onPlay() {
  gameRunning.value = true;
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}

async function onlyQuit() {
  window.history.back();
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  const script = document.createElement("script");
  script.src = "/assets/dosbox/main.js";

  script.onerror = () => {
    alert("Couldn't find dosbox script");
  };

  console.log(rom.value);

  downloadLink.value = getDownloadLink({
    rom: rom.value,
    fileIDs: downloadStore.fileIDsToDownload,
  });

  console.log(downloadLink.value);

  document.body.appendChild(script);
});
</script>

<template>
  <v-row v-if="rom" class="align-center justify-center scroll h-100" no-gutters>
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      class="bg-surface"
      rounded
    >
      <DosWasmX
        id="game"
        dos-wasm-url="/assets/dosbox/index.html"
        :rom-url="downloadLink"
        autostart
        :fullscreen="fullScreenOnPlay"
      ></DosWasmX>
    </v-col>

    <v-col
      cols="12"
      :sm="!gameRunning ? 10 : 10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row class="px-3 mt-6" no-gutters>
        <v-col>
          <v-divider class="my-4" />
          <rom-list-item :rom="rom" with-filename with-size />
          <v-divider class="my-4" />
        </v-col>
      </v-row>
      <v-row class="px-3 text-center" no-gutters>
        <v-col>
          <v-row class="align-center" no-gutters>
            <v-col>
              <v-btn
                block
                size="large"
                @click="onFullScreenChange"
                :disabled="gameRunning"
                :variant="fullScreenOnPlay ? 'flat' : 'outlined'"
                :color="fullScreenOnPlay ? 'primary' : ''"
                ><v-icon class="mr-1">{{
                  fullScreenOnPlay
                    ? "mdi-checkbox-outline"
                    : "mdi-checkbox-blank-outline"
                }}</v-icon
                >{{ t("play.full-screen") }}</v-btn
              >
            </v-col>
            <v-col
              cols="12"
              :sm="gameRunning ? 12 : 7"
              :xl="gameRunning ? 12 : 9"
              :class="gameRunning ? 'mt-2' : 'ml-2'"
            >
              <v-btn
                color="primary"
                block
                :disabled="gameRunning"
                variant="outlined"
                size="large"
                prepend-icon="mdi-play"
                @click="onPlay()"
                >{{ t("play.play") }}
              </v-btn>
            </v-col>
          </v-row>
          <v-row v-if="!gameRunning" class="align-center" no-gutters>
            <v-btn
              class="mt-4"
              block
              variant="outlined"
              size="large"
              prepend-icon="mdi-arrow-left"
              @click="
                $router.push({
                  name: ROUTES.ROM,
                  params: { rom: rom?.id },
                })
              "
              >{{ t("play.back-to-game-details") }}
            </v-btn>
            <v-btn
              class="mt-4"
              block
              variant="outlined"
              size="large"
              prepend-icon="mdi-arrow-left"
              @click="
                $router.push({
                  name: ROUTES.PLATFORM,
                  params: { platform: rom?.platform_id },
                })
              "
              >{{ t("play.back-to-gallery") }}
            </v-btn>
          </v-row>
          <v-btn
            v-if="gameRunning"
            class="mt-4"
            block
            variant="outlined"
            size="large"
            prepend-icon="mdi-exit-to-app"
            @click="onlyQuit"
          >
            {{ t("play.quit") }}
          </v-btn>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
#game-wrapper {
  height: 100%;
}

#game {
  height: 100%;
  --splash-screen-background: none;
}

@media (max-width: 960px) {
  #game-wrapper {
    height: calc(100vh - 55px);
  }
}
</style>
