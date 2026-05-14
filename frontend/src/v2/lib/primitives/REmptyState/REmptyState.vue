<script setup lang="ts">
// REmptyState — generic "nothing here yet" placeholder.
// Used wherever a list / panel can have zero items: media subtabs,
// save data subtabs, empty filters. Icon + title + optional hint +
// optional `actions` slot for CTAs (primitive contract: text via
// props/slots, no i18n inside).
import RIcon from "../../primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  icon?: string;
  title?: string;
  hint?: string;
  iconSize?: string | number;
  /** Size ladder shared with RBtn / RChip / RTag / Vuetify. */
  size?: "x-small" | "small" | "default" | "large" | "x-large";
}

withDefaults(defineProps<Props>(), {
  icon: "mdi-tray-remove",
  iconSize: 48,
  size: "default",
});
</script>

<template>
  <div class="r-empty-state" :class="`r-empty-state--${size}`">
    <slot name="icon">
      <RIcon :icon="icon" :size="iconSize" />
    </slot>
    <div v-if="title || $slots.title" class="r-empty-state__title">
      <slot name="title">{{ title }}</slot>
    </div>
    <div v-if="hint || $slots.hint" class="r-empty-state__hint">
      <slot name="hint">{{ hint }}</slot>
    </div>
    <div v-if="$slots.actions" class="r-empty-state__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.r-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--r-color-bg-elevated);
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
  text-align: center;
  color: var(--r-color-fg-muted);
}

/* Size ladder — same vocabulary as RBtn/RChip/RTag/RTabNav. Ramps both
   the box padding and the title typography step. */
.r-empty-state--x-small {
  padding: var(--r-space-4) var(--r-space-3);
  gap: var(--r-space-1);
}
.r-empty-state--small {
  padding: var(--r-space-6) var(--r-space-4);
  gap: var(--r-space-2);
}
.r-empty-state--default {
  padding: var(--r-space-10) var(--r-space-6);
  gap: var(--r-space-3);
}
.r-empty-state--large {
  padding: var(--r-space-12) var(--r-space-8);
  gap: var(--r-space-4);
}
.r-empty-state--x-large {
  padding: var(--r-space-14) var(--r-space-10);
  gap: var(--r-space-5);
}

.r-empty-state__title {
  color: var(--r-color-fg);
  font-weight: var(--r-font-weight-semibold);
}
.r-empty-state--x-small .r-empty-state__title {
  font-size: var(--r-font-size-sm);
}
.r-empty-state--small .r-empty-state__title {
  font-size: var(--r-font-size-md);
}
.r-empty-state--default .r-empty-state__title {
  font-size: var(--r-font-size-lg);
}
.r-empty-state--large .r-empty-state__title {
  font-size: var(--r-font-size-xl);
}
.r-empty-state--x-large .r-empty-state__title {
  font-size: var(--r-font-size-2xl);
}

.r-empty-state__hint {
  max-width: 440px;
  font-size: var(--r-font-size-sm);
  line-height: var(--r-line-height-relaxed);
}

.r-empty-state__actions {
  display: flex;
  gap: var(--r-space-2);
  flex-wrap: wrap;
  justify-content: center;
  margin-top: var(--r-space-2);
}
</style>
