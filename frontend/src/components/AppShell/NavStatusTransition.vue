<script setup lang="ts">
// Slides a top-bar status pill in and out. The host element gives the
// Transition a single root, since RMenu and RTooltip render fragments.
defineProps<{ show: boolean }>();
</script>

<template>
  <Transition name="r-nav-status">
    <div v-if="show" class="r-nav-status">
      <slot />
    </div>
  </Transition>
</template>

<style scoped>
.r-nav-status {
  display: flex;
}
.r-nav-status-enter-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-back);
}
.r-nav-status-leave-active {
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-nav-status-enter-from,
.r-nav-status-leave-to {
  opacity: 0;
  transform: translateX(10px) scale(0.9);
}
</style>
