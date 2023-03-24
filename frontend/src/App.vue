<script setup>
import { ref, inject, toRaw } from "vue"
import { useTheme } from "vuetify";
import Navigation from '@/components/Navigation.vue'

// Props
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'
const refresh = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('scanning', () => { refresh.value = !refresh.value })
</script>

<template>
  <v-app>
    
    <navigation :key="refresh"/>
    
    <v-main>
      <v-container fluid>
        <router-view :key="refresh"/>
      </v-container>
    </v-main>

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
