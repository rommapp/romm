<script setup lang="ts">
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);
const { t } = useI18n();
const navigationStore = storeNavigation();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const scanningStore = storeScanning();
const { scanningPlatforms, scanning } = storeToRefs(scanningStore);
const romsStore = storeRoms();
// Connect to socket on load to catch running scans
if (!socket.connected) socket.connect();

socket.on(
  "scan:scanning_platform",
  ({
    name,
    slug,
    id,
    fs_slug,
  }: {
    name: string;
    slug: string;
    id: number;
    fs_slug: string;
  }) => {
    scanningStore.set(true);
    scanningPlatforms.value = scanningPlatforms.value.filter(
      (platform) => platform.name !== name,
    );
    scanningPlatforms.value.push({ name, slug, id, fs_slug, roms: [] });
  },
);

socket.on("scan:scanning_rom", (rom: SimpleRom) => {
  scanningStore.set(true);
  romsStore.addToRecent(rom);
  if (romsStore.currentPlatform?.id === rom.platform_id) {
    romsStore.add([rom]);
  }

  let scannedPlatform = scanningPlatforms.value.find(
    (p) => p.slug === rom.platform_slug,
  );

  // Add the platform if the socket dropped and it's missing
  if (!scannedPlatform) {
    scanningPlatforms.value.push({
      name: rom.platform_name,
      slug: rom.platform_slug,
      id: rom.platform_id,
      fs_slug: rom.platform_fs_slug,
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
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('platforms.write')"
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-4 bg-background custom-btn"
    @click="navigationStore.goScan"
  >
    <div class="icon-container">
      <v-progress-circular
        v-if="scanning"
        color="primary"
        :width="2"
        :size="20"
        indeterminate
      />
      <v-icon v-else :color="$route.name == 'scan' ? 'primary' : ''"
        >mdi-magnify-scan</v-icon
      >
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption"
          :class="{ 'text-primary': $route.name == 'scan' }"
          >{{ t("scan.scan") }}</span
        >
      </v-expand-transition>
    </div>
  </v-btn>
</template>

<style scoped>
.custom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.icon-container span {
  text-align: center;
}
</style>
