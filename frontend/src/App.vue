<script setup lang="ts">
import NotificationStack from "@/layouts/NotificationStack.vue";
import Notification from "@/components/Notification.vue";
import api from "@/services/api/index";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { normalizeString } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted } from "vue";
import storeNotifications from "@/stores/notifications";

// Props
const scanningStore = storeScanning();
const notificationStore = storeNotifications();
const { notifications } = storeToRefs(notificationStore);
const { scanningPlatforms } = storeToRefs(scanningStore);
const romsStore = storeRoms();
const galleryFilter = storeGalleryFilter();
const isFiltered = normalizeString(galleryFilter.filterSearch).trim() != "";
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const configStore = storeConfig();
const auth = storeAuth();
const platformsStore = storePlatforms();

socket.on(
  "scan:scanning_platform",
  ({ name, slug, id }: { name: string; slug: string; id: number }) => {
    scanningStore.set(true);
    scanningPlatforms.value = scanningPlatforms.value.filter(
      (platform) => platform.name !== name
    );
    scanningPlatforms.value.push({ name, slug, id, roms: [] });
  }
);

socket.on("scan:scanning_rom", (rom: SimpleRom) => {
  scanningStore.set(true);
  if (romsStore.platformID === rom.platform_id) {
    romsStore.add([rom]);
    romsStore.setFiltered(
      isFiltered ? romsStore.filteredRoms : romsStore.allRoms,
      galleryFilter
    );
  }

  let scannedPlatform = scanningPlatforms.value.find(
    (p) => p.slug === rom.platform_slug
  );

  // Add the platform if the socket dropped and it's missing
  if (!scannedPlatform) {
    scanningPlatforms.value.push({
      name: rom.platform_name,
      slug: rom.platform_slug,
      id: rom.platform_id,
      roms: [],
    });
    scannedPlatform = scanningPlatforms.value[0];
  }

  scannedPlatform?.roms.push(rom);
});

socket.on("scan:done", () => {
  scanningStore.set(false);
  socket.disconnect();

  emitter?.emit("refreshDrawer", null);
  emitter?.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
    timeout: 4000,
  });
});

socket.on("scan:done_ko", (msg) => {
  scanningStore.set(false);

  emitter?.emit("snackbarShow", {
    msg: `Scan failed: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

onBeforeUnmount(() => {
  socket.off("scan:scanning_platform");
  socket.off("scan:scanning_rom");
  socket.off("scan:done");
  socket.off("scan:done_ko");
});

onMounted(() => {
  api.get("/heartbeat").then(({ data: data }) => {
    heartbeat.set(data);
  });

  api.get("/config").then(({ data: data }) => {
    configStore.set(data);
  });

  userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });

  platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });
});


</script>

<template>
  <v-app>
    <v-main>
      <!-- <notification /> -->
      <notification-stack />
      <v-btn
        @click="
          emitter?.emit('snackbarShow', {
            msg: 'test notification'+notifications.length,
            icon: 'mdi-check-bold',
            color: 'green',
          })
        "
        >Add</v-btn
      >
      <router-view />
    </v-main>
  </v-app>
</template>
<style lang="scss">
body {
  background-color: rgba(var(--v-theme-background)) !important;
}
.translucent {
  backdrop-filter: blur(3px) !important;
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000 !important;
}
.translucent-dark {
  background: rgba(0, 0, 0, 0.35) !important;
  backdrop-filter: blur(10px) !important;
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000 !important;
}
.tooltip :deep(.v-overlay__content) {
  background: rgba(255, 255, 255, 1) !important;
  color: rgb(41, 41, 41) !important;
}
.scroll {
  overflow-x: visible !important;
  overflow-y: scroll !important;
}
.emoji-collection {
  mask-image: linear-gradient(
    to right,
    black 0%,
    black 70%,
    transparent 100%
  ) !important;
}
.emoji {
  margin: 0 2px !important;
}
.file-input {
  display: none !important;
}
.transform-scale {
  transition-property: all !important;
  transition-duration: 0.1s !important;
}
.transform-scale.on-hover {
  z-index: 1 !important;
  transform: scale(1.05) !important;
}
.pointer {
  cursor: pointer !important;
}
</style>
