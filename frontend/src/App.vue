<script setup>
import { ref, onMounted  } from 'vue'
import { useTheme } from "vuetify";
import PlatformsBar from '@/components/PlatformsBar.vue'
import RomsGallery from '@/components/RomsGallery.vue'


const romsGalleryRef = ref(null)
const currentPlatform = localStorage.getItem('currentPlatform')
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'


function getRoms(platform){
  localStorage.setItem('currentPlatform', platform)
  romsGalleryRef.value.getRoms(platform)
}


onMounted(() => {
  if(currentPlatform){ getRoms(currentPlatform) }
})
</script>

<template>
  <v-app>
    
    <platforms-bar @currentPlatform="(platform) => getRoms(platform)"/>

    <v-main>
      <v-container fluid>
        <RomsGallery ref="romsGalleryRef" />
      </v-container>
    </v-main>

  </v-app>
</template>
