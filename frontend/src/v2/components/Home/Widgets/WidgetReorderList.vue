<script setup lang="ts">
// WidgetReorderList — small drag-and-drop list used inside Settings →
// Home → Widgets so users can decide left-to-right widget order on
// the Home dashboard rail. Native HTML5 drag API; the list is short
// (currently 2-5 entries) so a SortableJS dep would be overkill.
//
// The list shows every registered widget — disabled ones (gated off
// in their per-widget toggle) are still draggable so users can pick
// their preferred order before enabling them.
import { RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  parseWidgetOrder,
  serializeWidgetOrder,
  WIDGETS,
  type WidgetId,
} from "./widgets";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: string;
  /** Whether the master "show widgets bar" toggle is on. Drives the
   *  visual disabled state for the whole reorder list — drag still
   *  works (so users can prep their order while the bar is hidden)
   *  but the list reads as inert. */
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const { t } = useI18n();

const order = computed<WidgetId[]>(() => parseWidgetOrder(props.modelValue));

function entryFor(id: WidgetId) {
  return WIDGETS.find((w) => w.id === id);
}

// `dragIndex` tracks the row being lifted; `overIndex` tracks the
// hover target so the dragged-over row paints an insertion outline.
const dragIndex = ref<number | null>(null);
const overIndex = ref<number | null>(null);

function onDragStart(e: DragEvent, index: number) {
  dragIndex.value = index;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = "move";
    // Some browsers require any payload for drag to actually begin.
    e.dataTransfer.setData("text/plain", String(index));
  }
}

function onDragOver(e: DragEvent, index: number) {
  if (dragIndex.value === null) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
  overIndex.value = index;
}

function onDragLeave(index: number) {
  if (overIndex.value === index) overIndex.value = null;
}

function onDrop(e: DragEvent, index: number) {
  e.preventDefault();
  const from = dragIndex.value;
  dragIndex.value = null;
  overIndex.value = null;
  if (from === null || from === index) return;
  const next = [...order.value];
  const [moved] = next.splice(from, 1);
  next.splice(index, 0, moved);
  emit("update:modelValue", serializeWidgetOrder(next));
}

function onDragEnd() {
  dragIndex.value = null;
  overIndex.value = null;
}
</script>

<template>
  <ul
    class="r-v2-widget-reorder"
    :class="{ 'r-v2-widget-reorder--disabled': disabled }"
  >
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- HTML5 drag-and-drop is inherently pointer-driven; this is the drag affordance for reordering -->
    <li
      v-for="(id, i) in order"
      :key="id"
      class="r-v2-widget-reorder__row"
      :class="{
        'r-v2-widget-reorder__row--dragging': dragIndex === i,
        'r-v2-widget-reorder__row--over':
          overIndex === i && dragIndex !== null && dragIndex !== i,
      }"
      draggable="true"
      @dragstart="onDragStart($event, i)"
      @dragover="onDragOver($event, i)"
      @dragleave="onDragLeave(i)"
      @drop="onDrop($event, i)"
      @dragend="onDragEnd"
    >
      <RIcon
        icon="mdi-drag-vertical"
        size="14"
        class="r-v2-widget-reorder__handle"
        :aria-label="t('settings.widget-reorder-drag')"
      />
      <RIcon
        v-if="entryFor(id)?.icon"
        :icon="entryFor(id)!.icon"
        size="14"
        class="r-v2-widget-reorder__icon"
      />
      <span class="r-v2-widget-reorder__label">
        {{ entryFor(id) ? t(entryFor(id)!.labelKey) : id }}
      </span>
      <span class="r-v2-widget-reorder__pos">{{ i + 1 }}</span>
    </li>
  </ul>
</template>

<style scoped>
.r-v2-widget-reorder {
  list-style: none;
  margin: 0;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-widget-reorder--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.r-v2-widget-reorder__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  cursor: grab;
  user-select: none;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-widget-reorder__row:hover {
  background: var(--r-color-surface-hover);
}
.r-v2-widget-reorder__row:active {
  cursor: grabbing;
}
.r-v2-widget-reorder__row--dragging {
  opacity: 0.4;
  cursor: grabbing;
}
.r-v2-widget-reorder__row--over {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
}

.r-v2-widget-reorder__handle {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
.r-v2-widget-reorder__icon {
  color: var(--r-color-fg-secondary);
  flex-shrink: 0;
}
.r-v2-widget-reorder__label {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-widget-reorder__pos {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-muted);
  background: var(--r-color-bg-elevated);
  border-radius: 6px;
  padding: 2px 6px;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
</style>
