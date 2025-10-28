<script setup lang="ts">
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { ScanStats } from "@/__generated__";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";

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

// Batch ROM updates to prevent excessive re-renders
const romUpdateQueue = ref<SimpleRom[]>([]);
const processRomUpdates = debounce(() => {
  if (romUpdateQueue.value.length === 0) return;

  const updates = [...romUpdateQueue.value];
  romUpdateQueue.value = [];
  updates.forEach((rom) => {
    // Remove the ROM from the recent list and add it back to the top
    romsStore.removeFromRecent(rom);
    romsStore.addToRecent(rom);

    if (romsStore.currentPlatform?.id === rom.platform_id) {
      const existingRom = romsStore.filteredRoms.find((r) => r.id === rom.id);
      existingRom ? romsStore.update(rom) : romsStore.add([rom]);
    }

    let scannedPlatform = scanningPlatforms.value.find(
      (p) => p.slug === rom.platform_slug,
    );

    // Add the platform if the socket dropped and it's missing
    if (!scannedPlatform) {
      scanningPlatforms.value.push({
        display_name: rom.platform_display_name,
        slug: rom.platform_slug,
        id: rom.platform_id,
        fs_slug: rom.platform_fs_slug,
        is_identified: true,
        roms: [],
      });
      scannedPlatform = scanningPlatforms.value.at(-1)!;
    }

    // Check if ROM already exists in the store
    const existingRomInPlatform = scannedPlatform?.roms.find(
      (r) => r.id === rom.id,
    );
    if (existingRomInPlatform) {
      scannedPlatform.roms = scannedPlatform.roms.map((r) =>
        r.id === rom.id ? rom : r,
      );
    } else {
      scannedPlatform?.roms.push(rom);
    }
  });
}, 100);

socket.on(
  "scan:scanning_platform",
  ({
    display_name,
    slug,
    id,
    fs_slug,
    is_identified,
  }: {
    display_name: string;
    slug: string;
    id: number;
    fs_slug: string;
    is_identified: boolean;
  }) => {
    scanningStore.setScanning(true);
    scanningPlatforms.value = scanningPlatforms.value.filter(
      (platform) => platform.display_name !== display_name,
    );
    scanningPlatforms.value.push({
      display_name,
      slug,
      id,
      fs_slug,
      roms: [],
      is_identified,
    });
  },
);

socket.on("scan:scanning_rom", (rom: SimpleRom) => {
  scanningStore.setScanning(true);

  // Queue ROM for batch processing instead of immediate update
  romUpdateQueue.value.push(rom);
  processRomUpdates();
});

socket.on("scan:done", () => {
  scanningStore.setScanning(false);
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
  scanningStore.setScanning(false);

  emitter?.emit("snackbarShow", {
    msg: `Scan failed: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

socket.on("scan:update_stats", (stats: ScanStats) => {
  scanningStore.setScanStats(stats);
});

onBeforeUnmount(() => {
  socket.off("scan:scanning_platform");
  socket.off("scan:scanning_rom");
  socket.off("scan:done");
  socket.off("scan:done_ko");
  processRomUpdates.cancel();
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
    class="py-4 bg-background d-flex align-center justify-center"
    @click="navigationStore.goScan"
  >
    <div class="d-flex flex-column align-center">
      <v-progress-circular
        v-if="scanning"
        color="primary"
        :width="2"
        :size="20"
        indeterminate
      />
      <v-icon v-else :color="$route.name == 'scan' ? 'primary' : ''">
        mdi-magnify-scan
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': $route.name == 'scan' }"
          >{{ t("scan.scan") }}</span
        >
      </v-expand-transition>
    </div>
  </v-btn>
</template>
