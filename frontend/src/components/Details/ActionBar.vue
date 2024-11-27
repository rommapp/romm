<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import {
  getDownloadLink,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref, computed } from "vue";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const playInfoIcon = ref("mdi-play");

const ejsEmulationSupported = computed(() =>
  isEJSEmulationSupported(props.rom.platform_slug, heartbeatStore.value),
);
const ruffleEmulationSupported = computed(() =>
  isRuffleEmulationSupported(props.rom.platform_slug, heartbeatStore.value),
);

// Functions
async function copyDownloadLink(rom: DetailedRom) {
  const downloadLink =
    location.protocol +
    "//" +
    location.host +
    encodeURI(
      getDownloadLink({
        rom,
        files: downloadStore.filesToDownload,
      }),
    );
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(downloadLink);
    emitter?.emit("snackbarShow", {
      msg: "Download link copied to clipboard!",
      icon: "mdi-check-bold",
      color: "green",
      timeout: 2000,
    });
  } else {
    emitter?.emit("showCopyDownloadLinkDialog", downloadLink);
  }
}
</script>

<template>
  <v-btn-group divided density="compact" rounded="0" class="d-flex flex-row">
    <v-btn
      class="flex-grow-1"
      :disabled="downloadStore.value.includes(rom.id)"
      @click="
        romApi.downloadRom({
          rom,
          files: downloadStore.filesToDownload,
        })
      "
    >
      <v-tooltip
        activator="parent"
        location="top"
        transition="fade-transition"
        open-delay="1000"
        >Download game</v-tooltip
      >
      <v-icon icon="mdi-download" size="large" />
    </v-btn>
    <v-btn class="flex-grow-1" @click="copyDownloadLink(rom)">
      <v-tooltip
        activator="parent"
        location="top"
        transition="fade-transition"
        open-delay="1000"
        >Copy download link</v-tooltip
      >
      <v-icon icon="mdi-content-copy" />
    </v-btn>
    <v-btn
      v-if="ejsEmulationSupported"
      class="flex-grow-1"
      @click="
        $router.push({
          name: 'emulatorjs',
          params: { rom: rom?.id },
        })
      "
    >
      <v-icon :icon="playInfoIcon" />
    </v-btn>
    <v-btn
      v-if="ruffleEmulationSupported"
      class="flex-grow-1"
      @click="
        $router.push({
          name: 'ruffle',
          params: { rom: rom?.id },
        })
      "
    >
      <v-icon :icon="playInfoIcon" />
    </v-btn>
    <v-menu location="bottom">
      <template #activator="{ props: menuProps }">
        <v-btn class="flex-grow-1" v-bind="menuProps">
          <v-icon icon="mdi-dots-vertical" size="large" />
        </v-btn>
      </template>
      <admin-menu :rom="rom" />
    </v-menu>
  </v-btn-group>
</template>
