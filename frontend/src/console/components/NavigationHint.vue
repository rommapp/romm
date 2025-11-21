<script setup lang="ts">
import NavigationText from "./NavigationText.vue";

withDefaults(
  defineProps<{
    showNavigation?: boolean;
    showSelect?: boolean;
    showBack?: boolean;
    showToggleFavorite?: boolean;
    showMenu?: boolean;
    showDelete?: boolean;
  }>(),
  {
    showNavigation: true,
    showSelect: true,
    showBack: true,
    showToggleFavorite: false,
    showMenu: false,
    showDelete: false,
  },
);
</script>

<template>
  <div
    :style="{
      backgroundColor: 'var(--console-nav-hint-bg)',
      borderColor: 'var(--console-nav-hint-border)',
    }"
    class="fixed bottom-4 right-20 px-8 py-3 rounded-lg backdrop-blur border z-[100] pointer-events-none select-none"
  >
    <NavigationText
      :show-navigation="showNavigation"
      :show-select="showSelect"
      :show-back="showBack"
      :show-toggle-favorite="showToggleFavorite"
      :show-menu="showMenu"
      :show-delete="showDelete"
    />
  </div>
</template>
