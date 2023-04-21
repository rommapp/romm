<script setup>
import { ref, inject, onMounted } from "vue"
import { useTheme } from "vuetify"
import AppBar from '@/components/AppBar/Base.vue'
import MainDrawer from '@/components/MainDrawer/Base.vue'
import Notification from '@/components/Notification.vue'
import { getPlatforms } from '@/services/api.js'
import { storePlatforms } from '@/stores/platforms'

// Props
const platforms = storePlatforms()
useTheme().global.name.value = localStorage.getItem('theme') || 'rommDark'
const refresh = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('refresh', () => { refresh.value = !refresh.value })


onMounted(() => {
    getPlatforms()
    .then((res) => { platforms.add(res.data.data) })
    .catch((error) => { console.log(error);console.log("Couldn't fetch platforms") })
})
</script>

<template>
  <v-app>

    <app-bar/>

    <main-drawer :key="refresh"/>

    <v-main>
      <v-container fluid>
        <router-view :key="refresh"/>
      </v-container>
    </v-main>

    <notification class="mt-4"/>

  </v-app>
</template>

<style>
/* ===== Scrollbar CSS ===== */
/* Firefox */
* {
  scrollbar-width: none;
  /* scrollbar-width: thin; */
  scrollbar-color: #6e6e6e rgba(0, 0, 0, 0);;
}

/* Chrome, Edge, and Safari */
*::-webkit-scrollbar {
  width: 0px;
  /* width: 3px; */
}

*::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0);
}

*::-webkit-scrollbar-thumb {
  background-color: #808080;
  border-radius: 5px;
}
</style>
