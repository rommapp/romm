<script setup lang="ts">
import { ref, inject, onMounted } from "vue";
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
const platforms = storePlatforms();
const scanning = storeScanning();
const auth = storeAuth();
const refreshDrawer = ref(false);

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", () => {
  refreshDrawer.value = !refreshDrawer.value;
});

// Functions
onMounted(async () => {
  try {
    const { data: platformData } = await api.fetchPlatforms();
    platforms.set(platformData);
    const { data: userData } = await api.fetchCurrentUser();
    if (userData) auth.setUser(userData);
    emitter?.emit("refreshDrawer");
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

  <drawer :key="refreshDrawer" />

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
