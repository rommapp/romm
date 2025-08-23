<template>
  <div class="fixed bottom-4 right-20 bg-black/50 px-8 py-3 rounded-lg backdrop-blur border border-white/10 z-[100] pointer-events-none select-none">
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

<script setup lang="ts">
import NavigationText from './NavigationText.vue';

interface Props {
  showNavigation?: boolean;
  showSelect?: boolean;
  showBack?: boolean;
  showToggleFavorite?: boolean;
  showMenu?: boolean;
  showDelete?: boolean;
}

withDefaults(defineProps<Props>(), {
  showNavigation: true,
  showSelect: true,
  showBack: true,
  showToggleFavorite: false,
  showMenu: false,
  showDelete: false
});
</script>
