<script setup lang="ts">
// InfoGrid — two-column section grid used in the Overview tab.
// Each section is `icon + label` on the header line and a row of
// small chips below (genres, companies, franchises, collections, …).
// The icon gives each section a semantic anchor instead of relying
// on a plain uppercase eyebrow alone, and the chips have a clear
// hover affordance so they read as candidates for click-to-filter.
// Sections with no items are omitted so the grid doesn't show empty
// columns.
import { RIcon } from "@v2/lib";

defineOptions({ inheritAttrs: false });

export type InfoGridSection = {
  label: string;
  items: string[];
  /** Leading icon for the section header — gives each category a
   *  semantic cue (e.g. tags for genres, building for companies). */
  icon?: string;
};

const props = defineProps<{ sections: InfoGridSection[] }>();

const visible = () => props.sections.filter((s) => s.items.length > 0);
</script>

<template>
  <div v-if="visible().length" class="r-v2-det-infogrid">
    <div
      v-for="section in visible()"
      :key="section.label"
      class="r-v2-det-infogrid__item"
    >
      <div class="r-v2-det-infogrid__label">
        <RIcon
          v-if="section.icon"
          :icon="section.icon"
          size="13"
          class="r-v2-det-infogrid__label-icon"
        />
        <span>{{ section.label }}</span>
      </div>
      <div class="r-v2-det-infogrid__chips">
        <span
          v-for="item in section.items"
          :key="item"
          class="r-v2-det-infogrid__chip"
        >
          {{ item }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Auto-fill grid spanning the whole details body — sections reflow to a
   new row when the column would shrink below 240px. Mirrors the
   responsive pattern used by ProviderGrid in the Metadata tab so both
   surfaces feel like siblings. */
.r-v2-det-infogrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, auto));
  gap: 18px 24px;
  width: 100%;
}

.r-v2-det-infogrid__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  margin-bottom: 8px;
}
.r-v2-det-infogrid__label-icon {
  /* Brand-primary keeps the section header readable as a "label" cue
     against the muted eyebrow text — the icon is the focal point. */
  color: var(--r-color-brand-primary);
}

.r-v2-det-infogrid__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.r-v2-det-infogrid__chip {
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-chip);
  padding: 4px 10px;
  font-size: 11.5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-det-infogrid__chip:hover {
  color: var(--r-color-fg);
  border-color: var(--r-color-brand-primary);
  background: var(--r-color-surface-hover);
}
</style>
