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
    :color="activePlatformsDrawer ? 'toplayer' : 'background'"
    icon
    @click="navigationStore.switchActivePlatformsDrawer"
    class="rounded my-1"
    ><v-icon :color="$route.name == 'platform' ? 'primary' : ''"
      >mdi-controller</v-icon
    ></v-btn
  >
</template>
