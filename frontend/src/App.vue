<script setup>
import { ref } from 'vue'
import PlatformsBar from '@/components/PlatformsBar.vue'
const currentPlatform = ref("")
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
