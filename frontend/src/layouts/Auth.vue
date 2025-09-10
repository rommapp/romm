<script setup lang="ts">
import Notification from "@/components/common/Notifications/Notification.vue";
import storeHeartbeat from "@/stores/heartbeat";

const heartbeatStore = storeHeartbeat();
</script>

<template>
  <Notification />
  <v-container id="container" class="fill-height justify-center">
    <router-view />
  </v-container>
  <div id="version" class="position-absolute">
    <span class="text-white text-shadow">{{
      heartbeatStore.value.SYSTEM.VERSION
    }}</span>
  </div>
</template>

<style scoped>
#version {
  text-shadow:
    1px 1px 1px #000000,
    0 0 1px #000000;
  bottom: 0.3rem;
  right: 0.5rem;
}

#container {
  background-image: url("/assets/auth_background.svg");
  background-size: cover;
  background-position: center;
  max-width: 100vw;
}
</style>
