<script setup>
import { onBeforeMount } from "vue";
import { useTheme } from "vuetify";
import cookie from "js-cookie";
import { themes } from "@/styles/themes";
import storeAuth from "@/stores/auth";
import Notification from "@/components/Notification.vue";
import { api } from "./services/api";

// Props
const auth = storeAuth();

onBeforeMount(async () => {
  // Set CSRF token for all requests
  const { data } = await api.get("/heartbeat");
  auth.setEnabled(data.ROMM_AUTH_ENABLED ?? false);
  api.defaults.headers.common["x-csrftoken"] = cookie.get("csrftoken");
});

useTheme().global.name.value =
  themes[localStorage.getItem("theme")] || themes[0];
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
