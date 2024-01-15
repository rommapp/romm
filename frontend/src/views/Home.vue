<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onMounted } from "vue";
import { useDisplay } from "vuetify";

import AppBar from "@/components/AppBar/Base.vue";
import Drawer from "@/components/Drawer/Base.vue";
import api_user from "@/services/api_user";
import api_platform from "@/services/api_platform";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";

// Props
const { mdAndDown } = useDisplay();
const platformsStore = storePlatforms();
const scanning = storeScanning();
const auth = storeAuth();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await api_platform.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
onMounted(async () => {
  try {
    const { data: platforms } = await api_platform.getPlatforms();
    platformsStore.set(platforms);
    const { data: currentUser } = await api_user.fetchCurrentUser();
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
    :active="scanning.value"
    :indeterminate="true"
    absolute
    fixed
  />

  <drawer />

  <app-bar v-if="mdAndDown" />

  <v-container class="pa-0" fluid>
    <router-view />
  </v-container>
</template>

<style scoped>
#scan-progress-bar {
  z-index: 1000 !important;
}
</style>
