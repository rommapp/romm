<script setup>
import { onBeforeMount } from "vue";
import cookie from "js-cookie";
import storeAuth from "@/stores/auth";
import Notification from "@/components/Notification.vue";
import { api } from "@/services/api";

// Props
const auth = storeAuth();

onBeforeMount(async () => {
  // Set CSRF token for all requests
  const { data } = await api.get("/heartbeat");
  auth.setEnabled(data.ROMM_AUTH_ENABLED ?? false);
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
