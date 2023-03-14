<script setup>
import { ref, onMounted  } from 'vue'
import { useTheme } from "vuetify";
import PlatformsBar from '@/components/PlatformsBar.vue'
import RomsGallery from '@/components/RomsGallery.vue'


const romsGalleryRef = ref(null)
const currentPlatformSlug = localStorage.getItem('currentPlatformSlug') || ""
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'


function getRoms(platformSlug){
  romsGalleryRef.value.getRoms(platformSlug)
}


onMounted(() => {
  if(currentPlatformSlug){ getRoms(currentPlatformSlug) }
})
</script>

<template>
  <v-app>
    
    <platforms-bar @currentPlatformSlug="(platformSlug) => getRoms(platformSlug)"/>

    <v-main>
      <v-container fluid>
        <RomsGallery ref="romsGalleryRef" />
      </v-container>
    </v-main>

  </v-app>
</template>
