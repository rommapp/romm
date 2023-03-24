<script setup>
import { ref, inject } from "vue";
import { useTheme } from "vuetify";
import Navigation from '@/components/Navigation.vue'

// Props
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'
const scanning = ref(false)
</script>

<template>
  <v-app>
    
    <navigation/>
    
    <v-main>
      <v-container fluid>
        <router-view/>
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
  scrollbar-color: #808080 #ffffff;
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
  /* border: 3px solid #ffffff; */
}
</style>
