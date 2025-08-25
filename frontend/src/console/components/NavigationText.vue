<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import ArrowKeysIcon from "./icons/ArrowKeysIcon.vue";
import DPadIcon from "./icons/DPadIcon.vue";
import FaceButtons from "./icons/FaceButtons.vue";

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
  showDelete: false,
});

const hasController = ref(false);
let rafId = 0;

function poll() {
  const pads = navigator.getGamepads?.() || [];
  hasController.value = pads.some((p) => p && p.connected);
  rafId = requestAnimationFrame(poll);
}

onMounted(() => {
  window.addEventListener("gamepadconnected", poll);
  window.addEventListener("gamepaddisconnected", poll);
  poll();
});

onUnmounted(() => {
  cancelAnimationFrame(rafId);
  window.removeEventListener("gamepadconnected", poll);
  window.removeEventListener("gamepaddisconnected", poll);
});
</script>

<template>
  <div class="flex items-center gap-6 text-white/70 text-[12px]">
    <!-- Controller Mode -->
    <template v-if="hasController">
      <div v-if="showNavigation" class="flex items-center gap-2">
        <d-pad-icon class="w-8 h-8 opacity-80" />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <face-buttons highlight="south" />
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <face-buttons highlight="east" />
        <span class="font-medium tracking-wide">Back</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <face-buttons highlight="north" />
        <span class="font-medium tracking-wide">Favorite</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <face-buttons highlight="west" />
        <span class="font-medium tracking-wide">Menu</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <face-buttons highlight="west" />
        <span class="font-medium tracking-wide">Delete</span>
      </div>
    </template>
    <!-- Keyboard Mode -->
    <template v-else>
      <div v-if="showNavigation" class="flex items-center gap-2">
        <arrow-keys-icon />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <span class="keycap">Enter</span>
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <span class="keycap">Bkspc</span>
        <span class="font-medium tracking-wide">Back</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <span class="keycap">F</span>
        <span class="font-medium tracking-wide">Favorite</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <span class="keycap">X</span>
        <span class="font-medium tracking-wide">Menu</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <span class="keycap">X</span>
        <span class="font-medium tracking-wide">Delete</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.keycap {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 10px;
  font-family:
    ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo,
    monospace;
  font-weight: 700;
  letter-spacing: 0.05em;
}
</style>
