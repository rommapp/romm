<template>
  <svg
    viewBox="0 0 40 28"
    class="w-10 h-7"
    :style="{
      color: modal
        ? 'var(--console-nav-hint-modal-accent)'
        : 'var(--console-nav-hint-accent)',
    }"
    fill="none"
    stroke="currentColor"
  >
    <!-- Top arrow -->
    <g>
      <rect
        x="14"
        y="1"
        width="12"
        height="12"
        rx="2"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
          stroke: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
        }"
        stroke-width="0.5"
      />
      <path
        d="M 0 -3 L -2 -1 L -1 -1 L -1 3 L 1 3 L 1 -1 L 2 -1 Z"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-keycap)'
            : 'var(--console-nav-hint-keycap)',
        }"
        transform="translate(20, 7)"
      />
    </g>

    <!-- Left arrow -->
    <g>
      <rect
        x="1"
        y="14"
        width="12"
        height="12"
        rx="2"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
          stroke: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
        }"
        stroke-width="0.5"
      />
      <path
        d="M -3 0 L -1 -2 L -1 -1 L 3 -1 L 3 1 L -1 1 L -1 2 Z"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-keycap)'
            : 'var(--console-nav-hint-keycap)',
        }"
        transform="translate(7, 20)"
      />
    </g>

    <!-- Down arrow -->
    <g>
      <rect
        x="14"
        y="14"
        width="12"
        height="12"
        rx="2"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
          stroke: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
        }"
        stroke-width="0.5"
      />
      <path
        d="M 0 3 L -2 1 L -1 1 L -1 -3 L 1 -3 L 1 1 L 2 1 Z"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-keycap)'
            : 'var(--console-nav-hint-keycap)',
        }"
        transform="translate(20, 20)"
      />
    </g>

    <!-- Right arrow -->
    <g>
      <rect
        x="27"
        y="14"
        width="12"
        height="12"
        rx="2"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
          stroke: modal
            ? 'var(--console-nav-hint-modal-accent)'
            : 'var(--console-nav-hint-accent)',
        }"
        stroke-width="0.5"
      />
      <path
        d="M 3 0 L 1 -2 L 1 -1 L -3 -1 L -3 1 L 1 1 L 1 2 Z"
        :style="{
          fill: modal
            ? 'var(--console-nav-hint-modal-keycap)'
            : 'var(--console-nav-hint-keycap)',
        }"
        transform="translate(33, 20)"
      />
    </g>
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
