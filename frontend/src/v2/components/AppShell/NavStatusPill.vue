<script setup lang="ts">
// A link with `to`, a button otherwise; attrs land on that element so a
// tooltip or menu activator can bind to it.
import { RIcon, RProgressLinear } from "@v2/lib";
import { computed } from "vue";
import { RouterLink, type RouteLocationRaw } from "vue-router";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    label: string;
    /** Stands in for the label on phones. */
    icon: string;
    counter?: string | null;
    /** Percent done; null runs the bar indeterminate. */
    progress?: number | null;
    to?: RouteLocationRaw | undefined;
  }>(),
  { counter: null, progress: null, to: undefined },
);

const tag = computed(() => (props.to ? RouterLink : "button"));
</script>

<template>
  <component
    :is="tag"
    v-bind="$attrs"
    :to="to"
    :type="to ? undefined : 'button'"
    class="r-nav-status-pill"
  >
    <span class="r-nav-status-pill__row">
      <span class="r-nav-status-pill__label">{{ label }}</span>
      <RIcon
        :icon="icon"
        size="15"
        class="r-nav-status-pill__icon"
        aria-hidden="true"
      />
      <span v-if="counter">{{ counter }}</span>
    </span>

    <RProgressLinear
      class="r-nav-status-pill__progress"
      :indeterminate="progress === null"
      :model-value="progress ?? 0"
      :height="2"
      color="primary"
      :rounded="false"
      stream
    />
  </component>
</template>

<style scoped>
/* `isolation` keeps the bar out of any ancestor backdrop-filter layer;
   `overflow` trims its corners against the rounded pill. */
.r-nav-status-pill {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  height: var(--r-nav-pill-h);
  padding: 0 12px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border: 1px solid
    color-mix(in srgb, var(--r-color-brand-primary) 38%, transparent);
  color: var(--r-color-brand-primary);
  font: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  overflow: hidden;
  isolation: isolate;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-nav-status-pill:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
}

/* The row sits above the bottom-pinned bar, with a sliver of room
   between them. */
.r-nav-status-pill__row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  padding-bottom: 2px;
}

.r-nav-status-pill__label {
  white-space: nowrap;
}

/* The glyph replaces the label on phones. */
.r-nav-status-pill__icon {
  display: none;
}
html[data-bp~="xs"] .r-nav-status-pill__label {
  display: none;
}
html[data-bp~="xs"] .r-nav-status-pill__icon {
  display: inline-flex;
}

.r-nav-status-pill__progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}
</style>

<!-- Unscoped for the host's `<Transition name="r-nav-status-pill">`. Its child
     is a host element, since RMenu and RTooltip render fragments. -->
<style>
.r-nav-status-pill-host {
  display: flex;
}
.r-nav-status-pill-enter-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-back);
}
.r-nav-status-pill-leave-active {
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-nav-status-pill-enter-from,
.r-nav-status-pill-leave-to {
  opacity: 0;
  transform: translateX(10px) scale(0.9);
}
</style>
