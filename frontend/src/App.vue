<script setup lang="ts">
import Notification from "@/components/common/Notification.vue";
import api from "@/services/api/index";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeHeartbeat from "@/stores/heartbeat";
import RommIso from "@/components/common/RommIso.vue";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, normalizeString } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const { mdAndDown } = useDisplay();
const router = useRouter();
const auth = storeAuth();
const platformsDrawer = ref(false);
const settingsDrawer = ref(false);
const actionsDrawer = ref(false);
const navigationStore = storeNavigation();
const { activeSettingsDrawer, activePlatformsDrawer } = storeToRefs(navigationStore);
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const { scanningPlatforms } = storeToRefs(scanningStore);
const romsStore = storeRoms();
const galleryFilter = storeGalleryFilter();
const isFiltered = normalizeString(galleryFilter.filterSearch).trim() != "";
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const configStore = storeConfig();

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
  if (romsStore.currentPlatform?.id === rom.platform_id) {
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

// Functions
function goHome() {
  navigationStore.switchActivePlatformsDrawer(false)
  navigationStore.switchActiveSettingsDrawer(false)
  router.push({ name: "dashboard" });
}
function goScan() {
  navigationStore.switchActivePlatformsDrawer(false)
  navigationStore.switchActiveSettingsDrawer(false)
  router.push({ name: "dashboard" });
}
function togglePlatformsDrawer() {
  platformsDrawer.value = !platformsDrawer.value;
  settingsDrawer.value = false;
  actionsDrawer.value = false;
}
function toggleSettingsDrawer() {
  platformsDrawer.value = false;
  settingsDrawer.value = !settingsDrawer.value;
  actionsDrawer.value = false;
}
function toggleActionsDrawer() {
  platformsDrawer.value = false;
  settingsDrawer.value = false;
  actionsDrawer.value = !actionsDrawer.value;
}

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
});
</script>

<template>
  <v-app>
    <v-main>
      <v-progress-linear
        color="romm-accent-1"
        :active="scanning"
        :indeterminate="true"
        absolute
      />

      <notification />
      <!-- TODO: refactor and extract components -->
      <v-navigation-drawer
        :floating="platformsDrawer || settingsDrawer"
        rail
        rail-width="60"
      >
        <template #prepend>
          <v-row no-gutters class="my-2 justify-center">
            <router-link :to="{ name: 'dashboard' }">
              <v-hover v-slot="{ isHovering, props: hoverProps }">
                <romm-iso
                  v-bind="hoverProps"
                  :class="{ 'border-romm-accent-1': isHovering }"
                  :size="40"
                />
              </v-hover>
            </router-link>
          </v-row>
          <v-row no-gutters class="my-4 justify-center">
            <v-btn
              v-if="auth.scopes.includes('roms.write')"
              icon="mdi-upload"
              variant="flat"
              @click="emitter?.emit('showUploadRomDialog', null)"
            />
            <v-btn
              icon="mdi-magnify"
              variant="flat"
              @click="emitter?.emit('showSearchRomDialog', null)"
            />
          </v-row>
        </template>
        <v-row no-gutters class="justify-center">
          <v-btn
            block
            rounded="0"
            variant="flat"
            :color="platformsDrawer ? 'terciary' : ''"
            icon
            @click="togglePlatformsDrawer"
            ><v-icon :color="$route.name == 'platform' ? 'romm-accent-1' : ''"
              >mdi-controller</v-icon
            ></v-btn
          >
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            block
            rounded="0"
            variant="flat"
            color="primary"
            icon
            @click="goScan"
            ><v-icon :color="$route.name == 'scan' ? 'romm-accent-1' : ''"
              >mdi-magnify-scan</v-icon
            ></v-btn
          >
        </v-row>
        <template #append>
          <v-row no-gutters class="justify-center">
            <v-btn
              block
              rounded="0"
              variant="flat"
              :color="settingsDrawer ? 'terciary' : ''"
              icon
              @click="toggleSettingsDrawer"
              ><v-icon
                :color="
                  $route.name == 'settings' ||
                  $route.name == 'management' ||
                  $route.name == 'administration'
                    ? 'romm-accent-1'
                    : ''
                "
                >mdi-cog</v-icon
              ></v-btn
            >
            <v-avatar size="35" class="my-2">
              <v-img
                :src="
                  auth.user?.avatar_path
                    ? `/assets/romm/assets/${auth.user?.avatar_path}`
                    : defaultAvatarPath
                "
              />
            </v-avatar>
          </v-row>
        </template>
      </v-navigation-drawer>

      <router-view />

      <v-bottom-navigation
        v-if="mdAndDown"
        :elevation="0"
        class="bg-primary"
        mode="shift"
        height="45"
      >
        <v-btn @click="goHome">
          <v-icon>mdi-home</v-icon>
          <span>Home</span>
        </v-btn>
        <v-btn @click="togglePlatformsDrawer">
          <v-icon>mdi-controller</v-icon>
          <span>Platforms</span>
        </v-btn>
        <v-btn v-if="auth.scopes.includes('platforms.write')" @click="goScan">
          <v-icon>mdi-magnify-scan</v-icon>
          <span>Scan</span>
        </v-btn>
        <v-btn @click="toggleSettingsDrawer">
          <v-icon>mdi-cog</v-icon>
          <span>Settings</span>
        </v-btn>
        <v-btn @click="toggleActionsDrawer">
          <v-icon>mdi-dots-horizontal</v-icon>
          <span>Actions</span>
        </v-btn>
      </v-bottom-navigation>
    </v-main>
  </v-app>
</template>
<style scoped>
.v-progress-linear,
.v-bottom-navigation {
  z-index: 9999 !important;
}
</style>
