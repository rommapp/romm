<script setup lang="ts">
import AdminMenu from "@/components/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getDownloadLink, isEmulationSupported } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const emulation = ref(false);
const playInfoIcon = ref("mdi-play");
const emulationSupported = isEmulationSupported(props.rom.platform_slug);

function toggleEmulation() {
  emulation.value = !emulation.value;
  playInfoIcon.value = emulation.value ? "mdi-information" : "mdi-play";
  emitter?.emit("showEmulation", null);
}

async function copyDownloadLink(rom: DetailedRom) {
  const downloadLink =
    location.protocol +
    "//" +
    location.host +
    encodeURI(
      getDownloadLink({
        rom,
        files: downloadStore.filesToDownloadMultiFileRom,
      })
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
          files: downloadStore.filesToDownloadMultiFileRom,
        })
      "
    >
      <v-icon icon="mdi-download" size="large" />
    </v-btn>
    <v-btn class="flex-grow-1" @click="copyDownloadLink(rom)">
      <v-icon icon="mdi-content-copy" />
    </v-btn>
    <v-tooltip
      class="tooltip"
      text="Emulation not currently supported"
      location="bottom"
      :disabled="emulationSupported"
    >
      <template #activator="{ props: tooltipProps }">
        <v-btn
          class="flex-grow-1"
          :disabled="!emulationSupported"
          @click="toggleEmulation"
        >
          <v-icon :icon="playInfoIcon" />
        </v-btn>
      </template>
    </v-tooltip>
    <v-menu location="bottom">
      <template #activator="{ props: menuProps }">
        <v-btn
          class="flex-grow-1"
          :disabled="!auth.scopes.includes('roms.write')"
          v-bind="menuProps"
        >
          <v-icon icon="mdi-dots-vertical" size="large" />
        </v-btn>
      </template>
      <admin-menu :rom="rom" />
    </v-menu>
  </v-btn-group>
</template>
