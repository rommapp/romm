<template>
  <v-app>
    <platforms-bar />
    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
    </v-main>
</v-app>
</template>

<script setup>
import PlatformsBar from './components/PlatformsBar.vue'
</script>
