<script setup>
import { ref, inject, onMounted } from "vue";
import { useDisplay } from "vuetify";
import { fetchPlatformsApi, fetchCurrentUserApi } from "@/services/api.js";
import storePlatforms from "@/stores/platforms.js";
import storeScanning from "@/stores/scanning.js";
import storeAuth from "@/stores/auth.js";
import Drawer from "@/components/Drawer/Base.vue";
import AppBar from "@/components/AppBar/Base.vue";
import Notification from "@/components/Notification.vue";

// Props
const { mdAndDown } = useDisplay();
const platforms = storePlatforms();
const scanning = storeScanning();
const auth = storeAuth();
const refreshDrawer = ref(false);
const refreshView = ref(false);

// Event listeners bus
const emitter = inject("emitter");
emitter.on("refreshView", () => {
  refreshView.value = !refreshView.value;
});

// Functions
onMounted(async () => {
  try {
    const { data: platformData } = await fetchPlatformsApi();
    platforms.set(platformData);

    const { data: userData } = await fetchCurrentUserApi();
    if (userData) auth.setUser(userData);
  } catch (error) {
    console.error(error);
  }
});
</script>

<template>
  <notification class="mt-6" />

  <v-progress-linear
    id="scan-progress-bar"
    color="rommAccent1"
    :active="scanning.value"
    :indeterminate="true"
    absolute
    fixed
  />

  <drawer :key="refreshDrawer" />

  <app-bar v-if="mdAndDown" />

  <v-container class="pa-1" fluid>
    <router-view :key="refreshView" />
  </v-container>
</template>

<style scoped>
#scan-progress-bar {
  z-index: 1000 !important;
}
</style>
