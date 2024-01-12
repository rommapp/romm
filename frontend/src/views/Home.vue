<script setup lang="ts">
import { inject, onMounted } from "vue";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import api from "@/services/api";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeAuth from "@/stores/auth";
import Drawer from "@/components/Drawer/Base.vue";
import AppBar from "@/components/AppBar/Base.vue";

// Props
const { mdAndDown } = useDisplay();
const platformsStore = storePlatforms();
const scanning = storeScanning();
const auth = storeAuth();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
  emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await api.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
onMounted(async () => {
  try {
    const { data: platforms } = await api.getPlatforms();
    platformsStore.set(platforms);
    const { data: currentUser } = await api.fetchCurrentUser();
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
