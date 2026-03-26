<script setup lang="ts">
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";

const authStore = storeAuth();
const heartbeatStore = storeHeartbeat();

const retryFetchCurrentUser = () => {
  void authStore.fetchCurrentUser();
};
</script>

<template>
  <Notification />
  <v-container id="container" class="fill-height justify-center">
    <div v-if="authStore.isLoading" class="text-center">
      <v-progress-circular indeterminate color="primary" size="40" aria-label="Loading session" />
      <p class="mt-3 text-subtitle-1" aria-live="polite">Loading session...</p>
    </div>
    <div v-else-if="authStore.errorMessage" class="text-center">
      <v-alert type="error" variant="tonal" class="mb-4">
        {{ authStore.errorMessage }}
      </v-alert>
      <v-btn color="primary" @click="retryFetchCurrentUser">Retry</v-btn>
    </div>
    <router-view v-else />
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
