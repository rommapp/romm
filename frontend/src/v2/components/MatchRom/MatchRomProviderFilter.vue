<script setup lang="ts">
// Provider filter chip — toggleable square that paints a metadata
// provider's logo. Used as a row of filters above the matches grid:
// click toggles whether matches from that provider show up in the
// results. Disabled state covers providers the backend isn't
// configured for; inactive state is the user-driven "hide this
// provider" filter.
//
// Built as a feature composite with a real <button> root because the
// design (image-fills-the-square + opacity-driven muted state +
// brand-tinted active outline) doesn't fit RBtn's vocabulary
// (content-padded scale, hover/focus chrome). Wrapping RBtn here
// would require !important overrides on the primitive — see the
// "selectable surface" precedent we keep across the dialog flows.
import { RTooltip } from "@v2/lib";

defineOptions({ inheritAttrs: false });

defineProps<{
  name: string;
  label: string;
  logo: string;
  enabled: boolean;
  active: boolean;
}>();

const emit = defineEmits<{
  (e: "toggle"): void;
}>();
</script>

<template>
  <button
    type="button"
    class="provider-filter"
    :class="{
      'provider-filter--active': active && enabled,
      'provider-filter--disabled': !enabled,
    }"
    :disabled="!enabled"
    :aria-pressed="active"
    @click="emit('toggle')"
  >
    <img :src="logo" :alt="label" />
    <RTooltip
      activator="parent"
      :text="
        enabled ? `Filter ${label} matches` : `${label} source is not enabled`
      "
      :open-delay="400"
    />
  </button>
</template>

<style scoped>
.provider-filter {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border-strong);
  width: 32px;
  height: 32px;
  border-radius: var(--r-radius-sm);
  padding: 2px;
  cursor: pointer;
  display: grid;
  place-items: center;
  opacity: 0.4;
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.provider-filter:hover:not(:disabled) {
  opacity: 0.85;
  transform: translateY(-1px);
}
.provider-filter img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.provider-filter--active {
  opacity: 1;
  border-color: var(--r-color-brand-primary);
}
.provider-filter--active:hover {
  opacity: 1;
}
.provider-filter--disabled {
  cursor: not-allowed;
}
</style>
