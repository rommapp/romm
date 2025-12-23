<script setup lang="ts">
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import storeHeartbeat from "@/stores/heartbeat";

const heartbeatStore = storeHeartbeat();
</script>

<template>
  <Notification />
  <v-container id="container" class="fill-height justify-center">
    <router-view />
  </v-container>
  <div id="language-selector">
    <LanguageSelector density="compact" />
  </div>
  <span id="version" class="text-white text-subtitle-1 text-shadow">
    {{ heartbeatStore.value.SYSTEM.VERSION }}
  </span>
</template>

<style scoped>
#container {
  background-image: url("/assets/auth_background.svg");
  background-size: cover;
  background-position: center;
  max-width: 100vw;
  /* align-items: unset !important; */
}
#version {
  position: absolute !important;
  right: 15px !important;
  bottom: 10px !important;
}
#language-selector {
  position: absolute !important;
  left: 10px !important;
  bottom: 10px !important;
}
</style>
