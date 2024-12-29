<script setup lang="ts">
import Notification from "@/components/common/Notifications/Notification.vue";
import storeHeartbeat from "@/stores/heartbeat";

// Props
const heartbeatStore = storeHeartbeat();
</script>

<template>
  <span class="h-100 w-100 position-absolute" id="bg" />
  <notification />
  <v-container class="fill-height justify-center">
    <router-view />
  </v-container>
  <div id="version" class="position-absolute">
    <span class="text-white text-shadow">{{
      heartbeatStore.value.SYSTEM.VERSION
    }}</span>
  </div>
</template>

<style scoped>
#bg {
  background: url("/assets/login_bg.png") center center;
  background-size: cover;
}
#version {
  text-shadow:
    1px 1px 1px #000000,
    0 0 1px #000000;
  bottom: 0.3rem;
  right: 0.5rem;
}
</style>
