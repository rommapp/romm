<script setup>
import { onBeforeMount } from "vue";
import { useTheme } from "vuetify";
import axios from "axios";
import cookie from "js-cookie";
import { themes } from "@/styles/themes.js";

onBeforeMount(async () => {
  // Set CSRF token for all requests
  await axios.get("/api/heartbeat");
  axios.defaults.headers.common["x-csrftoken"] = cookie.get("csrftoken");
});

useTheme().global.name.value = themes[localStorage.getItem("theme")] || themes[0];
</script>

<template>
  <v-app>
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style>
@import "@/styles/scrollbar.css";
</style>
