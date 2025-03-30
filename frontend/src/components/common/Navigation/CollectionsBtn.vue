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
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
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
    :color="activeCollectionsDrawer ? 'toplayer' : 'background'"
    @click="navigationStore.switchActiveCollectionsDrawer"
  >
    <div class="icon-container">
      <v-icon :color="$route.name == 'collection' ? 'primary' : ''"
        >mdi-bookmark-box-multiple</v-icon
      >
      <span
        class="text-caption"
        :class="{ 'text-primary': $route.name == 'collection' }"
        >Collections</span
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
