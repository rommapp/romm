<script setup lang="ts">
import { useRouter } from "vue-router";

const props = defineProps<{
  text?: string;
  onBack?: () => void;
}>();

const router = useRouter();

function goBack() {
  if (props.onBack) props.onBack();
  else router.back();
}
</script>

<template>
  <div
    class="absolute top-4 left-4 z-30 inline-flex items-center pointer-events-none"
  >
    <button
      class="w-10 h-10 bg-black/60 border border-white/20 rounded-full flex items-center justify-center text-white hover:bg-white/10 hover:border-white/40 transition-all backdrop-blur pointer-events-auto"
      :aria-label="text ? `Back to ${text}` : 'Back'"
      @click="goBack"
    >
      <span aria-hidden="true" class="text-lg leading-none">←</span>
    </button>
    <span
      v-if="text"
      class="ml-3 text-white/90 text-3xl font-bold drop-shadow select-none"
    >
      {{ text }}
    </span>
  </div>
</template>
