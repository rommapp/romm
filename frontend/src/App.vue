<script setup>
import { ref, inject, onMounted } from "vue"
import { useTheme, useDisplay } from "vuetify"
import { fetchPlatforms } from '@/services/api.js'
import { storePlatforms } from '@/stores/platforms.js'
import { storeScanning } from '@/stores/scanning.js'
import Drawer from '@/components/Drawer/Base.vue'
import AppBar from '@/components/AppBar/Base.vue'
import Notification from '@/components/Notification.vue'

// Props
const platforms = storePlatforms()
const scanning = storeScanning()
const refresPlatforms = ref(false)
const refreshGallery = ref(false)
const { mdAndDown } = useDisplay()
useTheme().global.name.value = localStorage.getItem('theme') || 'rommDark'

// Event listeners bus
const emitter = inject('emitter')
emitter.on('refresPlatforms', () => {
  fetchPlatforms()
    .then((res) => { platforms.set(res.data.data) })
    .catch((error) => { console.log(error);console.log("Couldn't fetch platforms") })
    refresPlatforms.value = !refresPlatforms.value
})

emitter.on('refreshGallery', () => {
  refreshGallery.value = !refreshGallery.value
})


onMounted(() => {
  fetchPlatforms()
    .then((res) => { platforms.set(res.data.data) })
    .catch((error) => { console.log(error);console.log("Couldn't fetch platforms") })
})
</script>

<template>
  <v-app>

    <notification id="notification" class="mt-6"/>

    <v-progress-linear id="scan-progress-bar" color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute fixed/>

    <drawer id="drawer" :key="refresPlatforms"/>

    <app-bar v-if="mdAndDown"/>

    <v-main>
      <v-container class="pa-0" fluid>
          <router-view :key="refreshGallery"/>
      </v-container>
    </v-main>

  </v-app>
</template>

<style>
@import '@/styles/scrollbar.css';
#scan-progress-bar { z-index: 1000 !important; }
</style>
