<script setup>
import { ref, inject, onMounted } from "vue";
import { useDisplay } from "vuetify";
import Drawer from "@/components/Drawer/Base.vue";
import AppBar from "@/components/AppBar/Base.vue";
import Notification from "@/components/Notification.vue";
import { fetchPlatformsApi } from "@/services/api.js";
import storePlatforms from "@/stores/platforms.js";
import storeScanning from "@/stores/scanning.js";

// Props
const { mdAndDown } = useDisplay();
const platforms = storePlatforms();
const scanning = storeScanning();
const refreshPlatforms = ref(false);
const refreshGallery = ref(false);

// Event listeners bus
const emitter = inject("emitter");
emitter.on("refreshGallery", () => {
  refreshGallery.value = !refreshGallery.value;
});

onMounted(async () => {
  try {
    const { data } = await fetchPlatformsApi();
    platforms.set(data);
  } catch (error) {
    console.error("Couldn't fetch platforms:", error);
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

  <drawer :key="refreshPlatforms" />
  <app-bar v-if="mdAndDown" />
  <router-view :key="refreshGallery" />
</template>
