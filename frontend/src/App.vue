<script setup>
import { ref } from 'vue'
import { useTheme } from "vuetify";
import PlatformsBar from '@/components/PlatformsBar.vue'


const romsGalleryRef = ref(null)
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'


function getRoms(platformSlug){
  romsGalleryRef.value.getRoms(platformSlug)
}

</script>

<template>
  <v-app>
    
    <platforms-bar @currentPlatformSlug="(platformSlug) => getRoms(platformSlug)"/>

    <v-main>
      <v-container fluid>
        <router-view v-slot="{ Component }"> <component ref="romsGalleryRef" :is="Component" /></router-view>
      </v-container>
    </v-main>

  </v-app>
</template>

<style>
/* ===== Scrollbar CSS ===== */
/* Firefox */
* {
  scrollbar-width: none;
  scrollbar-color: #808080 #ffffff;
}

/* Chrome, Edge, and Safari */
*::-webkit-scrollbar {
  width: 0px;
}

*::-webkit-scrollbar-track {
  background: #ffffff;
}

*::-webkit-scrollbar-thumb {
  background-color: #808080;
  border-radius: 10px;
  border: 3px solid #ffffff;
}
</style>
