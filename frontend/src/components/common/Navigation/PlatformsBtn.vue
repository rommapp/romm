<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";

const navigationStore = storeNavigation();
const { activePlatformsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    rounded="0"
    variant="flat"
    :color="activePlatformsDrawer ? 'terciary' : ''"
    icon
    @click="navigationStore.switchActivePlatformsDrawer"
    ><v-icon :color="$route.name == 'platform' ? 'romm-accent-1' : ''"
      >mdi-controller</v-icon
    ></v-btn
  >
</template>
