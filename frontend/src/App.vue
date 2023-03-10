<script setup>
import { ref } from 'vue'
import { useTheme } from "vuetify";

import PlatformsBar from '@/components/PlatformsBar.vue'

var currentPlatform = ref("")
useTheme().global.name.value = localStorage.getItem('theme')
</script>

<template>
  <v-app>
    
    <platforms-bar @currentPlatform="(p) => currentPlatform=p"/>

    <v-main>
      <v-container fluid>
        <router-view :currentPlatform="currentPlatform" />
      </v-container>
    </v-main>

  </v-app>
</template>
