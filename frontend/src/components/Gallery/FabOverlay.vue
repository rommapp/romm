<script setup lang="ts">
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useRoute } from "vue-router";

// Props
const romsStore = storeRoms();
const galleryViewStore = storeGalleryView();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const { selectedRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const fabMenu = ref(false);
emitter?.on("openFabMenu", (open) => {
  fabMenu.value = open;
});
const auth = storeAuth();
const scanningStore = storeScanning();
const route = useRoute();
const heartbeat = storeHeartbeat();

// Functions
function scrollToTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}
async function onScan() {
  scanningStore.set(true);
  emitter?.emit("snackbarShow", {
    msg: `Scanning ${route.params.platform}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [route.params.platform],
    roms: romsStore.selectedRoms,
    type: "partial",
    apis: heartbeat.getMetadataOptions().map((s) => s.value),
  });
}

function selectAllRoms() {
  romsStore.setSelection(romsStore.filteredRoms);
}

function resetSelection() {
  romsStore.resetSelection();
  emitter?.emit("openFabMenu", false);
}

function onDownload() {
  romsStore.selectedRoms.forEach((rom) => {
    romApi.downloadRom({ rom });
  });
}
</script>

<template>
  <v-overlay
    :model-value="true"
    persistent
    scroll-strategy="reposition"
    :scrim="false"
    class="align-end justify-end pa-3"
  >
    <v-scroll-y-reverse-transition>
      <v-btn
        icon
        v-show="!scrolledToTop && currentView != 2"
        class="scroll-up-btn"
        color="primary"
        elevation="8"
        size="large"
        @click="scrollToTop()"
        ><v-icon color="romm-accent-1">mdi-chevron-up</v-icon></v-btn
      >
    </v-scroll-y-reverse-transition>

    <v-speed-dial v-model="fabMenu" transition="slide-y-transition">
      <template #activator="{ props: menuProps }">
        <v-fab-transition>
          <v-btn
            v-show="selectedRoms.length > 0"
            class="ml-2"
            color="romm-accent-1"
            v-bind="menuProps"
            elevation="8"
            icon
            size="large"
            >{{ selectedRoms.length }}</v-btn
          >
        </v-fab-transition>
      </template>

      <v-btn
        key="1"
        v-if="auth.scopes.includes('roms.write')"
        color="terciary"
        elevation="8"
        icon
        size="default"
        @click="emitter?.emit('showDeleteRomDialog', romsStore.selectedRoms)"
      >
        <v-icon color="romm-red"> mdi-delete </v-icon>
      </v-btn>
      <v-btn
        key="2"
        color="terciary"
        elevation="8"
        icon
        size="default"
        @click="onDownload"
      >
        <v-icon>mdi-download</v-icon>
      </v-btn>
      <v-btn
        key="3"
        v-if="auth.scopes.includes('roms.write')"
        color="terciary"
        elevation="8"
        icon
        size="default"
        @click="onScan"
      >
        <v-icon>mdi-magnify-scan</v-icon>
      </v-btn>
      <v-btn
        key="4"
        color="terciary"
        elevation="8"
        icon="mdi-select-all"
        size="default"
        @click.stop="selectAllRoms"
      />
      <v-btn
        key="5"
        color="terciary"
        elevation="8"
        icon="mdi-select"
        size="default"
        @click.stop="resetSelection"
      />
    </v-speed-dial>
  </v-overlay>
</template>
<style scoped>
.scroll-up-btn {
  border: 1px solid rgba(var(--v-theme-romm-accent-1));
}
</style>
