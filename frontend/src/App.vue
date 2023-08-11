<script setup>
import { ref, inject, onMounted, onBeforeUpdate, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useTheme, useDisplay } from "vuetify";
import { fetchPlatformsApi } from "@/services/api.js";
import storePlatforms from "@/stores/platforms.js";
import storeScanning from "@/stores/scanning.js";
import Login from "@/views/Login.vue";
import Drawer from "@/components/Drawer/Base.vue";
import AppBar from "@/components/AppBar/Base.vue";
import Notification from "@/components/Notification.vue";

// Props
const router = useRouter();
const route = useRoute();
const logged = ref(
  localStorage.getItem("login") === "true"
); /* TODO: implement authentication session logic */
const platforms = storePlatforms();
const scanning = storeScanning();
const refreshPlatforms = ref(false);
const refreshGallery = ref(false);
const { mdAndDown } = useDisplay();
useTheme().global.name.value = localStorage.getItem("theme") || "rommDark";

// Event listeners bus
const emitter = inject("emitter");
emitter.on("login", (isLogged) => {
  router.isReady();
  logged.value = isLogged;
});

emitter.on("refreshPlatforms", async () => {
  try {
    const { data } = await fetchPlatformsApi();
    platforms.set(data);
  } catch (error) {
    console.error("Couldn't fetch platforms:", error);
  } finally {
    refreshPlatforms.value = !refreshPlatforms.value;
  }
});

emitter.on("refreshGallery", () => {
  refreshGallery.value = !refreshGallery.value;
});

async function checkLogin() {
  if (logged.value) {
    try {
      const { data } = await fetchPlatformsApi();
      platforms.set(data);
    } catch (error) {
      console.error("Couldn't fetch platforms:", error);
    }
  } else {
    await router.push("/login");
  }
}
onMounted(async () => {
  await checkLogin();
});
onBeforeUpdate(async () => {
  await checkLogin();
});
</script>

<template>
  <template v-if="logged">
    <v-app>
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

      <v-main>
        <v-container id="main-container" class="pa-1" fluid>
          <router-view :key="refreshGallery" />
        </v-container>
      </v-main>
    </v-app>
  </template>

  <template v-else>
    <login />
  </template>
</template>

<style>
@import "@/styles/scrollbar.css";

#scan-progress-bar {
  z-index: 1000 !important;
}

#main-container {
  height: 100%;
}
</style>
