<template>
  <div class="fixed bottom-4 right-20 flex gap-6 text-white/60 text-sm bg-black/80 px-6 py-3 rounded-lg backdrop-blur z-[100]">
    <span
      v-for="hint in hints"
      :key="hint"
    >
      {{ hint }}
    </span>
  </div>
</template>
<script setup lang="ts">
const props = defineProps<{ hints?: string[] }>();
const hints = props.hints ?? [];
</script>
