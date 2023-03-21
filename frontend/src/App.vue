<script setup>
import { useTheme } from "vuetify";
import Navigation from '@/components/Navigation.vue'

// Props
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'
</script>

<template>
  <v-app>
    
    <navigation/>

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
