<script setup lang="ts">
import storeNavigation from "@/stores/navigation";

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
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    rounded="1"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-2 my-1 bg-background custom-btn"
    @click="navigationStore.goSearch"
  >
    <div class="icon-container">
      <v-icon :color="$route.name == 'search' ? 'primary' : ''"
        >mdi-magnify</v-icon
      >
      <span
        class="text-caption"
        :class="{ 'text-primary': $route.name == 'search' }"
        >Search</span
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
