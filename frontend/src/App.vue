<script setup>
import { ref, inject } from "vue"
import { useTheme } from "vuetify"
import Navigation from '@/components/Navigation.vue'

// Props
useTheme().global.name.value = localStorage.getItem('theme') || 'dark'
const refresh = ref(false)
const refreshRoms = ref(false)
const snackbarShow = ref(false)
const snackbarStatus = ref({})

// Event listeners bus
const emitter = inject('emitter')
emitter.on('refresh', () => { refresh.value = !refresh.value })
emitter.on('refreshRoms', () => { refreshRoms.value = !refreshRoms.value })
emitter.on('snackbarScan', (snackbar) => {
  snackbarShow.value = true
  snackbarStatus.value = snackbar
})
</script>

<template>
  <v-app>
    
    <navigation :key="refresh"/>
    
    <v-main>
      <v-container fluid>
        <router-view :key="refreshRoms"/>
      </v-container>
    </v-main>

    <v-snackbar v-model="snackbarShow" :timeout="3000">
        <v-icon :icon="snackbarStatus.icon" :color="snackbarStatus.color" class="ml-2 mr-2"/>
        {{ snackbarStatus.msg }}
        <template v-slot:actions>
            <v-btn variant="text" @click="snackbarShow = false"><v-icon icon="mdi-close"/></v-btn>
        </template>
    </v-snackbar>

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
