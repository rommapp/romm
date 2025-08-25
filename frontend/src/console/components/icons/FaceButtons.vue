<template>
  <svg viewBox="0 0 24 24" class="w-8 h-8 text-white/70 translate-y-[1px]">
    <!-- North button (Y/Triangle) -->
    <circle
      cx="12"
      cy="4"
      r="4"
      :class="highlight === 'north' ? 'fill-white/70' : 'fill-white/15'"
    />

    <!-- South button (A/Cross) -->
    <circle
      cx="12"
      cy="20"
      r="4"
      :class="highlight === 'south' ? 'fill-white/70' : 'fill-white/15'"
    />

    <!-- West button (X/Square) -->
    <circle
      cx="4"
      cy="12"
      r="4"
      :class="highlight === 'west' ? 'fill-white/70' : 'fill-white/15'"
    />

    <!-- East button (B/Circle) -->
    <circle
      cx="20"
      cy="12"
      r="4"
      :class="highlight === 'east' ? 'fill-white/70' : 'fill-white/15'"
    />
  </svg>
</template>

<script setup lang="ts">
interface Props {
  highlight?: "north" | "south" | "west" | "east";
}

withDefaults(defineProps<Props>(), {
  highlight: "south",
});
</script>
