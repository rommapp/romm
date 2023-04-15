<script setup>
import { ref, inject } from "vue"
import { useTheme } from "vuetify"
import AppBar from '@/components/AppBar/Base.vue'
import PlatformsDrawer from '@/components/PlatformsDrawer/Base.vue'
import SettingsDrawer from '@/components/SettingsDrawer/Base.vue'
import Notification from '@/components/Notification.vue'

// Props
useTheme().global.name.value = localStorage.getItem('theme') || 'rommDark'
const refresh = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('refresh', () => { refresh.value = !refresh.value })
</script>

<template>
  <v-app>

    <settings-drawer/>

    <app-bar/>

    <platforms-drawer :key="refresh"/>

    <v-main>
      <v-container fluid>
        <router-view :key="refresh"/>
      </v-container>
    </v-main>

    <notification/>

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

rommDark {
  primary:      #161b22;
  secondary:    #a452fe;
  background:   #0d1117;

  notification: #0d1117;
  surface:      #161b22;
  tooltip:      #161b22;
  chip:         #161b22;
  
  rommAccent1:  #a452fe;
  rommAccent2:  #9a00ea;
  rommAccent3:  #7b00e1;
  rommAccent4:  #702bcf;
  rommAccent5:  #3808a4;
  rommWhite:    #fefdfe;
  rommBlack:    #000000;
  rommRed:      #da3633;
}

</style>
