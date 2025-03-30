<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
  },
);
const navigationStore = storeNavigation();
const { activePlatformsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    rounded="1"
    :height="height"
    class="py-2 my-1 bg-background custom-btn"
    :class="{ rounded: rounded }"
    :color="activePlatformsDrawer ? 'toplayer' : 'background'"
    @click="navigationStore.switchActivePlatformsDrawer"
  >
    <div class="icon-container">
      <v-icon :color="$route.name == 'platform' ? 'primary' : ''"
        >mdi-controller</v-icon
      >
      <span
        class="text-caption"
        :class="{ 'text-primary': $route.name == 'platform' }"
        >Platforms</span
      >
    </div>
  </v-btn>
</template>

<style scoped>
.custom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.icon-container span {
  text-align: center;
}
</style>
