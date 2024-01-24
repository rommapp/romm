<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onMounted } from "vue";
import { useDisplay } from "vuetify";

import AppBar from "@/components/AppBar/Base.vue";
import Drawer from "@/components/Drawer/Base.vue";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";

// Props
const { mdAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const auth = storeAuth();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
onMounted(async () => {
  try {
    const { data: platforms } = await platformApi.getPlatforms();
    platformsStore.set(platforms);
    const { data: currentUser } = await userApi.fetchCurrentUser();
    if (currentUser) auth.setUser(currentUser);
    emitter?.emit("refreshDrawer", null);
  } catch (error) {
    console.error(error);
  }
});
</script>

<template>
  <v-progress-linear
    id="scan-progress-bar"
    color="romm-accent-1"
    :active="scanning"
    :indeterminate="true"
    absolute
    fixed
  />
  <drawer />
  <app-bar v-if="mdAndDown" />
  <router-view />
</template>

<style scoped>
#scan-progress-bar {
  z-index: 1001 !important;
}
</style>
