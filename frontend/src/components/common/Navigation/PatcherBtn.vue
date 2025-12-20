<script setup lang="ts">
import storeNavigation from "@/stores/navigation";

withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);

const navigationStore = storeNavigation();
</script>

<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-4 bg-background d-flex align-center justify-center"
    @click="navigationStore.goPatcher"
  >
    <div class="d-flex flex-column align-center">
      <v-icon :color="$route.path.startsWith('/patcher') ? 'primary' : ''">
        mdi-memory-arrow-down
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': $route.path.startsWith('/patcher') }"
        >
          Patcher
        </span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>
