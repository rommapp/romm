{"file_path":"frontend/src/layouts/Auth.vue"}{"file_path":"frontend/src/layouts/Auth.vue"}<script setup lang="ts">
import LanguageSelector from "@/components/common/LanguageSelector.vue";
import { storeHeartbeat } from "@/stores/heartbeat";

const heartbeatStore = storeHeartbeat();
</script>

<template>
  <div class="d-flex justify-end pa-5">
    <LanguageSelector density="compact" />
  </div>
  <span id="version" class="text-white text-subtitle-1 text-shadow">
    {{ heartbeatStore.value.SYSTEM?.VERSION }}
  </span>
</template>