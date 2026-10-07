<script setup lang="ts">
// RSortHeader: one column header of a sortable list. The parent owns the sort
// state and the row grid; this owns `aria-sort`, the button and the glyph.
import { computed, useSlots } from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import { nextSortDir } from "./nextSortDir";
import type { RSortDir, RSortHeaderProps } from "./types";

defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<RSortHeaderProps>(), {
  sortable: false,
  active: false,
  dir: "asc",
  align: "start",
  hideLabel: false,
});

const emit = defineEmits<{
  (e: "sort", dir: RSortDir): void;
}>();

defineSlots<{
  /** Adornment after the label, e.g. a help button. */
  append?: () => unknown;
}>();

const slots = useSlots();

const ariaSort = computed(() => {
  if (!props.sortable) return undefined;
  if (!props.active) return "none";
  return props.dir === "asc" ? "ascending" : "descending";
});
</script>

<template>
  <div
    class="r-sort-header"
    :class="[
      `r-sort-header--${align}`,
      { 'r-sort-header--has-append': !!slots.append },
    ]"
    role="columnheader"
    :aria-sort="ariaSort"
    v-bind="$attrs"
  >
    <button
      v-if="sortable"
      type="button"
      class="r-sort-header__btn"
      :class="{ 'r-sort-header__btn--active': active }"
      @click="emit('sort', nextSortDir(active, dir))"
    >
      <span
        class="r-sort-header__label"
        :class="{ 'r-sort-header__label--hidden': hideLabel }"
      >
        {{ label }}
      </span>
      <RIcon
        v-if="active"
        :icon="dir === 'asc' ? 'mdi-arrow-up-thin' : 'mdi-arrow-down-thin'"
        size="14"
        class="r-sort-header__icon"
      />
    </button>
    <span
      v-else
      class="r-sort-header__label"
      :class="{ 'r-sort-header__label--hidden': hideLabel }"
    >
      {{ label }}
    </span>

    <slot name="append" />
  </div>
</template>

<style scoped>
.r-sort-header {
  display: flex;
  align-items: center;
  gap: var(--r-space-1);
  min-width: 0;
  height: 100%;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.r-sort-header--end {
  justify-content: flex-end;
  text-align: end;
}
.r-sort-header--center {
  justify-content: center;
  text-align: center;
}

/* The button fills the cell so the whole header is the hit target, unless an
   adornment has to sit right after the label. */
.r-sort-header__btn {
  flex: 1;
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  text-align: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: inherit;
  gap: var(--r-space-1);
  min-width: 0;
  height: 100%;
  cursor: pointer;
  border-radius: var(--r-radius-sm);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-sort-header--has-append .r-sort-header__btn {
  flex: 0 1 auto;
}
.r-sort-header__btn:hover,
.r-sort-header__btn:focus-visible,
.r-sort-header__btn--active {
  color: var(--r-color-fg);
}

.r-sort-header__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-sort-header__label--hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.r-sort-header__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
/* End-aligned labels hug the right edge, so the glyph goes on the label's
   left. Appending it would shove the label sideways on click. */
.r-sort-header--end .r-sort-header__icon {
  order: -1;
}
</style>
