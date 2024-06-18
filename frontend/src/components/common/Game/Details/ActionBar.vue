<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getDownloadLink, isEmulationSupported } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const playInfoIcon = ref("mdi-play");
const emulationSupported = isEmulationSupported(props.rom.platform_slug);

// Functions
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
    <v-btn
      v-if="emulationSupported"
      class="flex-grow-1"
      @click="
        $router.push({
          name: 'play',
          params: { rom: rom?.id },
        })
      "
    >
      <v-icon :icon="playInfoIcon" />
    </v-btn>
    <v-menu location="bottom">
      <template #activator="{ props: menuProps }">
        <v-btn
          v-if="auth.scopes.includes('roms.write')"
          class="flex-grow-1"
          v-bind="menuProps"
        >
          <v-icon icon="mdi-dots-vertical" size="large" />
        </v-btn>
      </template>
      <admin-menu :rom="rom" />
    </v-menu>
  </v-btn-group>
</template>
