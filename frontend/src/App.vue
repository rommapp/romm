<script setup lang="ts">
import { onBeforeMount } from "vue";
import cookie from "js-cookie";
import storeAuth from "@/stores/auth";
import Notification from "@/components/Notification.vue";
import { api } from "@/services/api";
import storeHeartbeat from "@/stores/heartbeat";

// Props
const auth = storeAuth();
const heartbeat = storeHeartbeat();

onBeforeMount(async () => {
  const { data } = await api.get("/heartbeat");
  heartbeat.set(data)
  auth.setEnabled(data.ROMM_AUTH_ENABLED ?? false);
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
