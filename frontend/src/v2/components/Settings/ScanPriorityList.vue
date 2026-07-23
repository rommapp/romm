<script setup lang="ts">
// ScanPriorityList — orders a fixed set of metadata/artwork providers by
// priority. The model is the ordered list of *enabled* provider slugs
// (first = highest priority); providers absent from it are disabled and
// shown in an "add" tray below.
//
// Reordering supports every input modality: pointer drag (HTML5 DnD) and
// explicit move-up / move-down buttons (keyboard, gamepad, touch). Modelled
// on Home/Widgets/WidgetReorderList but adds enable/disable.
import { RBtn, RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

interface Source {
  value: string;
  label: string;
}

const props = withDefaults(
  defineProps<{
    modelValue: string[];
    sources: Source[];
    disabled?: boolean;
  }>(),
  { disabled: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const { t } = useI18n();

const labelFor = (value: string) =>
  props.sources.find((s) => s.value === value)?.label ?? value;

// Enabled = model order; available = sources not in the model, in the
// canonical `sources` order so the tray stays stable.
const enabled = computed(() => props.modelValue);
const available = computed(() =>
  props.sources.filter((s) => !props.modelValue.includes(s.value)),
);

function emitNext(next: string[]) {
  emit("update:modelValue", next);
}

function move(index: number, delta: number) {
  const target = index + delta;
  if (target < 0 || target >= enabled.value.length) return;
  const next = [...enabled.value];
  [next[index], next[target]] = [next[target], next[index]];
  emitNext(next);
}

function remove(value: string) {
  emitNext(enabled.value.filter((v) => v !== value));
}

function add(value: string) {
  if (enabled.value.includes(value)) return;
  emitNext([...enabled.value, value]);
}

// ── Drag reordering (pointer only; buttons cover other modalities) ──
const dragIndex = ref<number | null>(null);
const overIndex = ref<number | null>(null);

function onDragStart(e: DragEvent, index: number) {
  if (props.disabled) return;
  dragIndex.value = index;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = "move";
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
  const next = [...enabled.value];
  const [moved] = next.splice(from, 1);
  next.splice(index, 0, moved);
  emitNext(next);
}

function onDragEnd() {
  dragIndex.value = null;
  overIndex.value = null;
}
</script>

<template>
  <div class="r-v2-spl" :class="{ 'r-v2-spl--disabled': disabled }">
    <ul v-if="enabled.length" class="r-v2-spl__list">
      <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- drag is pointer-only; move buttons provide the keyboard/gamepad path -->
      <li
        v-for="(value, i) in enabled"
        :key="value"
        class="r-v2-spl__row"
        :class="{
          'r-v2-spl__row--dragging': dragIndex === i,
          'r-v2-spl__row--over':
            overIndex === i && dragIndex !== null && dragIndex !== i,
        }"
        :draggable="!disabled"
        @dragstart="onDragStart($event, i)"
        @dragover="onDragOver($event, i)"
        @dragleave="onDragLeave(i)"
        @drop="onDrop($event, i)"
        @dragend="onDragEnd"
      >
        <RIcon
          icon="mdi-drag-vertical"
          size="14"
          class="r-v2-spl__handle"
          :aria-label="t('settings.scan-priority-drag')"
        />
        <span class="r-v2-spl__pos">{{ i + 1 }}</span>
        <span class="r-v2-spl__label">{{ labelFor(value) }}</span>
        <div class="r-v2-spl__actions">
          <RBtn
            variant="text"
            size="x-small"
            icon="mdi-chevron-up"
            :disabled="disabled || i === 0"
            :aria-label="
              t('settings.scan-priority-move-up', { name: labelFor(value) })
            "
            @click="move(i, -1)"
          />
          <RBtn
            variant="text"
            size="x-small"
            icon="mdi-chevron-down"
            :disabled="disabled || i === enabled.length - 1"
            :aria-label="
              t('settings.scan-priority-move-down', { name: labelFor(value) })
            "
            @click="move(i, 1)"
          />
          <RBtn
            variant="text"
            size="x-small"
            icon="mdi-close"
            class="r-v2-spl__remove"
            :disabled="disabled"
            :aria-label="
              t('settings.scan-priority-disable', { name: labelFor(value) })
            "
            @click="remove(value)"
          />
        </div>
      </li>
    </ul>
    <p v-else class="r-v2-spl__empty">
      {{ t("settings.scan-priority-none-enabled") }}
    </p>

    <div v-if="available.length" class="r-v2-spl__tray">
      <span class="r-v2-spl__tray-label">
        {{ t("settings.scan-priority-add") }}
      </span>
      <div class="r-v2-spl__tray-items">
        <button
          v-for="source in available"
          :key="source.value"
          type="button"
          class="r-v2-spl__add"
          :disabled="disabled"
          @click="add(source.value)"
        >
          <RIcon icon="mdi-plus" size="12" />
          <span>{{ source.label }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-v2-spl {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}
.r-v2-spl--disabled {
  opacity: 0.55;
  pointer-events: none;
}

.r-v2-spl__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-spl__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  user-select: none;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-spl__row--dragging {
  opacity: 0.4;
}
.r-v2-spl__row--over {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
}

.r-v2-spl__handle {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
  cursor: grab;
}
.r-v2-spl__row--dragging .r-v2-spl__handle {
  cursor: grabbing;
}

.r-v2-spl__pos {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-muted);
  background: var(--r-color-bg-elevated);
  border-radius: 6px;
  padding: 2px 6px;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.r-v2-spl__label {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-spl__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.r-v2-spl__remove {
  color: color-mix(in srgb, var(--r-color-danger) 70%, transparent) !important;
}
.r-v2-spl__remove:hover {
  color: var(--r-color-danger) !important;
}

.r-v2-spl__empty {
  margin: 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}

.r-v2-spl__tray {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--r-color-border);
  padding-top: 12px;
}
.r-v2-spl__tray-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}
.r-v2-spl__tray-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.r-v2-spl__add {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px dashed var(--r-color-border-strong);
  background: transparent;
  color: var(--r-color-fg-secondary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-spl__add:hover {
  border-color: var(--r-color-brand-primary);
  color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
</style>
