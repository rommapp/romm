<script setup>
import { useTheme } from "vuetify";
import { themes } from "@/styles/themes.js";

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
