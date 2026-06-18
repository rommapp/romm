<script setup lang="ts">
// CollectionPickerRow — one row in the ManageCollectionsDialog. Portrait
// thumb + name + rom-count + brand-primary circular tick when checked.
// Click toggles; parent owns the pending/checked state and handles the
// API round-trip.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  name: string;
  count: number;
  covers: string[];
  /** Membership state of the row against the current selection:
   *   - "off"  → none of the selected ROMs are in this collection
   *   - "some" → some are, some aren't (bulk-only, drawn with a dash)
   *   - "all"  → every selected ROM is already in this collection */
  state: "off" | "some" | "all";
  busy?: boolean;
  // Thumb diameter in px. Drives both the grid first-column width and
  // the CollectionMosaic width so the label column always lines up with
  // the right edge of the thumb.
  tileSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  busy: false,
  tileSize: 36,
});

defineEmits<{
  (e: "toggle"): void;
}>();

const rowStyle = computed(() => ({
  "--tile-w": `${props.tileSize}px`,
}));

const isOn = computed(() => props.state !== "off");
const isPartial = computed(() => props.state === "some");
const isFull = computed(() => props.state === "all");
</script>

<template>
  <button
    type="button"
    class="pick-row"
    :class="{
      'pick-row--checked': isFull,
      'pick-row--partial': isPartial,
      'pick-row--busy': busy,
    }"
    :style="rowStyle"
    :aria-pressed="isFull"
    :aria-checked="isPartial ? 'mixed' : isFull"
    :disabled="busy"
    @click="$emit('toggle')"
  >
    <CollectionMosaic :covers="covers" radius="6px" class="pick-row__thumb" />
    <span class="pick-row__name">{{ name }}</span>
    <span class="pick-row__count">{{ count }}</span>
    <span class="pick-row__tick" aria-hidden="true">
      <RIcon
        v-if="isOn"
        :icon="isPartial ? 'mdi-minus' : 'mdi-check'"
        size="14"
      />
    </span>
  </button>
</template>

<style scoped>
.pick-row {
  appearance: none;
  width: 100%;
  background: transparent;
  border: 0;
  display: grid;
  grid-template-columns: var(--tile-w, 36px) 1fr auto 26px;
  align-items: center;
  gap: 14px;
  padding: 8px 16px;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font-family: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.pick-row:hover {
  background: var(--r-color-bg-elevated);
}
.pick-row--checked {
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.pick-row--checked:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
}
.pick-row--busy {
  opacity: 0.6;
  cursor: progress;
}

/* Portrait thumb — width tracks the configurable tile size; height is
   computed by CollectionMosaic from its 140/188 aspectRatio. */
.pick-row__thumb {
  width: var(--tile-w, 36px);
}

.pick-row__name {
  min-width: 0;
  font-size: 14px;
  color: var(--r-color-fg);
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pick-row__count {
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-medium);
}

.pick-row__tick {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid var(--r-color-surface-hover);
  color: transparent;
  background: transparent;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.pick-row--checked .pick-row__tick {
  background: var(--r-color-brand-primary);
  border-color: var(--r-color-brand-primary);
  color: var(--r-color-overlay-fg);
}

/* Indeterminate (`some`) — the brand colour reads as a hint but the
   tick swaps to a horizontal dash so users can tell "partially in" from
   "fully in" at a glance. */
.pick-row--partial .pick-row__tick {
  background: color-mix(in srgb, var(--r-color-brand-primary) 25%, transparent);
  border-color: var(--r-color-brand-primary);
  color: var(--r-color-brand-primary);
}
.pick-row--partial {
  background: color-mix(in srgb, var(--r-color-brand-primary) 4%, transparent);
}
.pick-row--partial:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
}

:global(.r-v2.r-v2-light) .pick-row__name {
  color: color-mix(in srgb, var(--r-color-fg) 92%, transparent);
}
:global(.r-v2.r-v2-light) .pick-row__count {
  color: color-mix(in srgb, var(--r-color-fg) 50%, transparent);
}
:global(.r-v2.r-v2-light) .pick-row:hover {
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}
:global(.r-v2.r-v2-light) .pick-row__tick {
  border-color: color-mix(in srgb, var(--r-color-fg) 15%, transparent);
}
</style>
