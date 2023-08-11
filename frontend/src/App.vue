<script setup>
import { useTheme } from "vuetify";

useTheme().global.name.value = localStorage.getItem("theme") || "rommDark";
</script>

<template>
  <v-app>
    <v-main>
      <v-container id="main-container" class="pa-1" fluid>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
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
