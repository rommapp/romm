<script setup lang="ts">
import Notification from "@/components/Notification.vue";
import { api } from "@/services/api";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import { onBeforeMount } from "vue";
import cookie from "js-cookie";

// Props
const authStore = storeAuth();
const heartbeatStore = storeHeartbeat();
const configStore = storeConfig();

onBeforeMount(async () => {
  const { data: heartBeatData } = await api.get("/heartbeat");
  heartbeatStore.set(heartBeatData);
  authStore.setEnabled(heartBeatData.ROMM_AUTH_ENABLED ?? false);
  const { data: configData } = await api.get("/config");
  configStore.set(configData);
  // Set CSRF token for all requests
  api.defaults.headers.common["x-csrftoken"] = cookie.get("csrftoken");
});
</script>

<template>
  <v-app>
    <v-main>
      <notification class="mt-6" />
      <router-view />
    </v-main>
  </v-app>
</template>

<style>
@import "@/styles/scrollbar.css";
</style>
