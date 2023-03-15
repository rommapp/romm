<script setup>
import { ref } from 'vue'
import { useTheme } from "vuetify";
import PlatformsBar from '@/components/PlatformsBar.vue'


const platformsBar = ref(null)
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'


async function getRoms(platformSlug){
  await router.push(import.meta.env.BASE_URL)
  viewComponent.value.getRoms(platformSlug)
}

async function gettingRoms(flag){
  platformsBar.value.gettingRoms(flag)
}

async function getRomDetails(rom) {
  
  viewComponent.value.getRomDetails(rom)
}
</script>

<template>
  <v-app>
    
    <platforms-bar/>

    <v-main>
      <v-container fluid>
        <router-view />
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
