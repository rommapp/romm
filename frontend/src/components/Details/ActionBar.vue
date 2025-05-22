<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import CopyRomDownloadLinkDialog from "@/components/common/Game/Dialog/CopyDownloadLink.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeHeartbeat from "@/stores/heartbeat";
import storeConfig from "@/stores/config";
import type { DetailedRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import {
  getDownloadLink,
  is3DSCIARom,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { storeToRefs } from "pinia";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const playInfoIcon = ref("mdi-play");
const qrCodeIcon = ref("mdi-qrcode");
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const auth = storeAuth();

const platformSlug = computed(() =>
  props.rom.platform_slug in config.value.PLATFORMS_VERSIONS
    ? config.value.PLATFORMS_VERSIONS[props.rom.platform_slug]
    : props.rom.platform_slug,
);

const ejsEmulationSupported = computed(() => {
  return isEJSEmulationSupported(platformSlug.value, heartbeatStore.value);
});

const ruffleEmulationSupported = computed(() => {
  return isRuffleEmulationSupported(platformSlug.value, heartbeatStore.value);
});

const is3DSRom = computed(() => {
  return is3DSCIARom(props.rom);
});

// Functions
async function copyDownloadLink(rom: DetailedRom) {
  const downloadLink = getDownloadLink({
    rom,
    fileIDs: downloadStore.fileIDsToDownload,
  });
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
  <div>
    <v-btn-group divided density="compact" rounded="0" class="d-flex flex-row">
      <v-btn
        class="flex-grow-1"
        :disabled="downloadStore.value.includes(rom.id)"
        @click="
          romApi.downloadRom({
            rom,
            fileIDs: downloadStore.fileIDsToDownload,
          })
        "
        :aria-label="`Download ${rom.name}`"
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
      <v-btn
        :aria-label="`Copy download link ${rom.name}`"
        class="flex-grow-1"
        @click="copyDownloadLink(rom)"
      >
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
        :aria-label="`Play ${rom.name}`"
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
        :aria-label="`Play ${rom.name}`"
      >
        <v-icon :icon="playInfoIcon" />
      </v-btn>
      <v-btn
        v-if="is3DSRom"
        class="flex-grow-1"
        @click="emitter?.emit('showQRCodeDialog', rom)"
        :aria-label="`Show ${rom.name} QR code`"
      >
        <v-icon :icon="qrCodeIcon" />
      </v-btn>
      <v-menu
        v-if="
          auth.scopes.includes('roms.write') ||
          auth.scopes.includes('roms.user.write') ||
          auth.scopes.includes('collections.write')
        "
        location="bottom"
      >
        <template #activator="{ props: menuProps }">
          <v-btn
            :aria-label="`${rom.name} admin menu`"
            class="flex-grow-1"
            v-bind="menuProps"
          >
            <v-icon icon="mdi-dots-vertical" size="large" />
          </v-btn>
        </template>
        <admin-menu :rom="rom" />
      </v-menu>
    </v-btn-group>

    <copy-rom-download-link-dialog />
  </div>
</template>
