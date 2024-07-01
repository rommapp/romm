<script setup lang="ts">
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
  }>(),
  {
    block: false,
  }
);
const navigationStore = storeNavigation();
const auth = storeAuth();
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('platforms.write')"
    :block="block"
    rounded="0"
    variant="flat"
    color="primary"
    icon
    @click="navigationStore.goScan"
    ><v-icon :color="$route.name == 'scan' ? 'romm-accent-1' : ''"
      >mdi-magnify-scan</v-icon
    ></v-btn
  >
</template>
