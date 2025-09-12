<template>
  <svg
    viewBox="0 0 40 40"
    fill="none"
    :style="{ color: 'var(--console-button-text-muted)' }"
  >
    <!-- Top arrow -->
    <rect
      x="16"
      y="4"
      width="8"
      height="12"
      rx="2"
      :style="{
        fill: modal
          ? 'var(--console-nav-hint-modal-keycap)'
          : 'var(--console-nav-hint-keycap)',
      }"
    />

    <!-- Bottom arrow -->
    <rect
      x="16"
      y="24"
      width="8"
      height="12"
      rx="2"
      :style="{
        fill: modal
          ? 'var(--console-nav-hint-modal-keycap)'
          : 'var(--console-nav-hint-keycap)',
      }"
    />

    <!-- Left arrow -->
    <rect
      x="4"
      y="16"
      width="12"
      height="8"
      rx="2"
      :style="{
        fill: modal
          ? 'var(--console-nav-hint-modal-keycap)'
          : 'var(--console-nav-hint-keycap)',
      }"
    />

    <!-- Right arrow -->
    <rect
      x="24"
      y="16"
      width="12"
      height="8"
      rx="2"
      :style="{
        fill: modal
          ? 'var(--console-nav-hint-modal-keycap)'
          : 'var(--console-nav-hint-keycap)',
      }"
    />

    <!-- Center button -->
    <rect
      x="16"
      y="16"
      width="8"
      height="8"
      rx="2"
      :style="{
        fill: modal
          ? 'var(--console-nav-hint-modal-accent)'
          : 'var(--console-nav-hint-accent)',
      }"
    />
  </svg>
</template>

<script setup lang="ts">
interface Props {
  modal?: boolean;
}

withDefaults(defineProps<Props>(), {
  modal: false,
});
</script>
