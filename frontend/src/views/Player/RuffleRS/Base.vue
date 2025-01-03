<script setup lang="ts">
import RomListItem from "@/components/common/Game/ListItem.vue";
import romApi from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeGalleryView from "@/stores/galleryView";
import type { DetailedRom } from "@/stores/roms";
import { isNull } from "lodash";
import { storeToRefs } from "pinia";
import { nextTick, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

const RUFFLE_VERSION = "0.1.0-nightly.2024.12.28";

// Props
const { t } = useI18n();
const route = useRoute();
const galleryViewStore = storeGalleryView();
const heartbeat = storeHeartbeat();
const { defaultAspectRatioScreenshot } = storeToRefs(galleryViewStore);
const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

declare global {
  interface Window {
    RufflePlayer: any;
  }
}

window.RufflePlayer = window.RufflePlayer || {};

// Functions
function onPlay() {
  gameRunning.value = true;

  nextTick(() => {
    const ruffle = window.RufflePlayer.newest();
    const player = ruffle.createPlayer();
    const container = document.getElementById("game");
    container?.appendChild(player);
    player.load({
      allowFullScreen: true,
      autoplay: "on",
      backgroundColor: "#0D1117",
      openUrlMode: "confirm",
      publicPath: "/assets/ruffle/",
      url: `/api/roms/${rom.value?.id}/content/${rom.value?.file_name}`,
    });
    player.style.width = "100%";
    player.style.height = "100%";

    if (player.fullscreenEnabled && fullScreenOnPlay.value) {
      player.enterFullscreen();
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

  const script = document.createElement("script");
  script.src = "/assets/ruffle/ruffle.js";

  script.onerror = () => {
    const fallbackScript = document.createElement("script");
    fallbackScript.src =
      "https://unpkg.com/@ruffle-rs/ruffle@${RUFFLE_VERSION}/ruffle.js";
    document.body.appendChild(fallbackScript);
  };

  document.body.appendChild(script);
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
      :style="`aspect-ratio: ${defaultAspectRatioScreenshot}`"
      class="bg-secondary"
      rounded
    >
      <div id="game" />
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
          <rom-list-item :rom="rom" with-filename />
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
                >{{ t("play.full-screen") }}</v-btn
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
                >{{ t("play.play") }}
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
            >{{ t("play.reset-session") }}
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
            >{{ t("play.back-to-game-details") }}
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
            >{{ t("play.back-to-gallery") }}
          </v-btn>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
#game {
  max-height: 100dvh;
  height: 100%;
  --splash-screen-background: none;
}
</style>
