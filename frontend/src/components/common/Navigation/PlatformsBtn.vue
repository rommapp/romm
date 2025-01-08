<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";

withDefaults(
  defineProps<{
    block?: boolean;
  }>(),
  {
    block: false,
  },
);
const navigationStore = storeNavigation();
const { activePlatformsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    :block="block"
    variant="flat"
    :color="activePlatformsDrawer ? 'toplayer' : ''"
    icon
    @click="navigationStore.switchActivePlatformsDrawer"
    ><v-icon :color="$route.name == 'platform' ? 'primary' : ''"
      >mdi-controller</v-icon
    ></v-btn
  >
</template>
