<script setup lang="ts">
// RLetterHeading — small uppercase faint label used to separate
// letter-grouped sections in galleries (ROM list, Platforms,
// Collections). Generic on purpose: the consumer passes the label as a
// prop or default slot, so it can paint a single letter ("A"), a digit
// bucket ("#"), or any short section anchor without the primitive
// knowing what's underneath.
defineOptions({ inheritAttrs: false });

interface Props {
  /** Label text. Falls back to the default slot when not set. */
  label?: string;
}

withDefaults(defineProps<Props>(), {
  label: undefined,
});
</script>

<template>
  <div class="r-letter-heading" v-bind="$attrs">
    <slot>{{ label }}</slot>
  </div>
</template>

<style scoped>
.r-letter-heading {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  padding: 20px 0 12px;
}
</style>
