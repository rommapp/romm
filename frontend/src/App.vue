<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from "vuetify";
import PlatformsBar from '@/components/PlatformsBar.vue'


const router = useRouter()
const viewComponent = ref(null)
const platformsBar = ref(null)
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'


async function getRoms(platformSlug){
  await router.push('/')
  viewComponent.value.getRoms(platformSlug)
}

async function gettingRoms(flag){
  platformsBar.value.gettingRoms(flag)
}

async function getRomDetails(rom) {
  await router.push('/details')
  viewComponent.value.getRomDetails(rom)
}
</script>

<template>
  <v-app>
    
    <platforms-bar ref="platformsBar" @currentPlatformSlug="(platformSlug) => getRoms(platformSlug)"/>

    <v-main>
      <v-container fluid>
        <router-view v-slot="{ Component }">
          <component ref="viewComponent" :is="Component" @currentRom="(rom) => getRomDetails(rom)" @gettingRoms="(flag) => gettingRoms(flag)"/>
        </router-view>
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
