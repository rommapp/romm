<template>
  <svg
    viewBox="0 0 24 24"
    class="w-8 h-8 translate-y-[1px]"
    :style="{ color: 'var(--console-button-text-muted)' }"
  >
    <!-- North button (Y/Triangle) -->
    <circle
      cx="12"
      cy="4"
      r="4"
      :style="{
        fill:
          highlight === 'north'
            ? modal
              ? 'var(--console-nav-hint-modal-keycap)'
              : 'var(--console-nav-hint-keycap)'
            : modal
              ? 'var(--console-nav-hint-modal-accent)'
              : 'var(--console-nav-hint-accent)',
      }"
    />

    <!-- South button (A/Cross) -->
    <circle
      cx="12"
      cy="20"
      r="4"
      :style="{
        fill:
          highlight === 'south'
            ? modal
              ? 'var(--console-nav-hint-modal-keycap)'
              : 'var(--console-nav-hint-keycap)'
            : modal
              ? 'var(--console-nav-hint-modal-accent)'
              : 'var(--console-nav-hint-accent)',
      }"
    />

    <!-- West button (X/Square) -->
    <circle
      cx="4"
      cy="12"
      r="4"
      :style="{
        fill:
          highlight === 'west'
            ? modal
              ? 'var(--console-nav-hint-modal-keycap)'
              : 'var(--console-nav-hint-keycap)'
            : modal
              ? 'var(--console-nav-hint-modal-accent)'
              : 'var(--console-nav-hint-accent)',
      }"
    />

    <!-- East button (B/Circle) -->
    <circle
      cx="20"
      cy="12"
      r="4"
      :style="{
        fill:
          highlight === 'east'
            ? modal
              ? 'var(--console-nav-hint-modal-keycap)'
              : 'var(--console-nav-hint-keycap)'
            : modal
              ? 'var(--console-nav-hint-modal-accent)'
              : 'var(--console-nav-hint-accent)',
      }"
    />
  </svg>
</template>

<script setup lang="ts">
interface Props {
  highlight?: "north" | "south" | "west" | "east";
  modal?: boolean;
}

withDefaults(defineProps<Props>(), {
  highlight: "south",
  modal: false,
});
</script>
