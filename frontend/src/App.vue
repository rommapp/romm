<script setup>
import { useTheme } from "vuetify";

useTheme().global.name.value = localStorage.getItem("theme") || "rommDark";
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
