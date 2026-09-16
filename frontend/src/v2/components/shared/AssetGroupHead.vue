<script setup lang="ts">
// Group head shared by <AssetList> (slots) and <AssetStrip> (cores), so the
// two Save data subtabs line up: icon, title, chips, count and fold chevron.
import { RIcon } from "@v2/lib";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    icon: string;
    /** Brand for slots, warning for cores, muted for the archive. */
    iconTone?: "brand" | "warning" | "muted";
    title: string;
    count: string | number;
    /** Renders the head as a fold button. Off, the chevron only keeps its
     *  space so counts line up across groups. */
    foldable?: boolean;
    expanded?: boolean;
    /** Greys the title of a group nothing can be picked from. */
    muted?: boolean;
  }>(),
  { iconTone: "brand", foldable: false, expanded: false, muted: false },
);

const emit = defineEmits<{ toggle: [] }>();
</script>

<template>
  <component
    :is="foldable ? 'button' : 'div'"
    :type="foldable ? 'button' : undefined"
    class="r-asset-group-head"
    :class="{ 'r-asset-group-head--static': !foldable }"
    :aria-expanded="foldable ? expanded : undefined"
    v-bind="$attrs"
    @click="foldable && emit('toggle')"
  >
    <RIcon
      :icon="icon"
      size="14"
      class="r-asset-group-head__icon"
      :class="`r-asset-group-head__icon--${iconTone}`"
    />
    <span
      class="r-asset-group-head__title"
      :class="{ 'r-asset-group-head__title--muted': muted }"
    >
      {{ title }}
    </span>
    <slot />
    <span class="r-asset-group-head__count">{{ count }}</span>
    <RIcon
      icon="mdi-chevron-down"
      size="16"
      class="r-asset-group-head__chevron"
      aria-hidden="true"
    />
  </component>
</template>

<style scoped>
.r-asset-group-head {
  appearance: none;
  border: 0;
  background: none;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px;
  border-radius: var(--r-radius-sm);
  font: inherit;
  text-align: left;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-asset-group-head:hover {
  background: color-mix(in srgb, var(--r-color-fg) 8%, transparent);
}
.r-asset-group-head--static,
.r-asset-group-head--static:hover {
  background: none;
  cursor: default;
}

.r-asset-group-head__icon--brand {
  color: var(--r-color-brand-primary);
}
/* Same tone as the emulator tag on the tiles. */
.r-asset-group-head__icon--warning {
  color: var(--r-color-warning);
}
.r-asset-group-head__icon--muted {
  color: var(--r-color-fg-muted);
}

.r-asset-group-head__title {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-group-head__title--muted {
  color: var(--r-color-fg-muted);
}

.r-asset-group-head__count {
  margin-left: auto;
  font-size: 10px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.r-asset-group-head__chevron {
  transition: transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-asset-group-head--static .r-asset-group-head__chevron {
  visibility: hidden;
}
.r-asset-group-head[aria-expanded="true"] .r-asset-group-head__chevron {
  transform: rotate(180deg);
}
</style>
