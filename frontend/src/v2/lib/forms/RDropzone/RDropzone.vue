<script setup lang="ts">
// RDropzone — file drag-and-drop target with the shared v2 upload vocabulary
// (dashed brand border, cloud icon, click-to-browse). Two modes:
//
//   * CTA (default): renders an empty-state call-to-action — icon, title,
//     hint, and click/keyboard to browse. The whole surface is the drop
//     target and brightens while dragging over it.
//   * Overlay (`overlay` prop): renders the default slot (the consumer's
//     filled content — a file list, a grid, a card) and floats a "release to
//     upload" overlay over it while dragging. Use the exposed `open()` to wire
//     an explicit add/replace button.
//
// Emits `files` on drop or pick. Primitive: no stores/i18n — all copy comes
// from props so consumers pass translated strings.
import { useDropZone } from "@vueuse/core";
import { ref } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Allow selecting / dropping more than one file. */
  multiple?: boolean;
  /** `accept` attribute for the underlying file input (e.g. "image/*"). */
  accept?: string;
  /** MIME types passed to the drop filter; omit to accept anything. */
  dataTypes?: string[];
  disabled?: boolean;
  /** Overlay mode: render the default slot + a drag-over overlay. */
  overlay?: boolean;
  // CTA copy / icons (ignored in overlay mode except `activeIcon`).
  title?: string;
  hint?: string;
  icon?: string;
  activeIcon?: string;
  /** Title swapped in while dragging over the CTA (falls back to `title`). */
  activeTitle?: string;
  /** Overlay caption shown while dragging over filled content. */
  releaseLabel?: string;
  /** Accessible label for the underlying (visually hidden) file input. */
  inputLabel?: string;
}

const props = withDefaults(defineProps<Props>(), {
  multiple: false,
  icon: "mdi-cloud-upload-outline",
  activeIcon: "mdi-cloud-upload",
});

const emit = defineEmits<{ files: [files: File[]] }>();

defineSlots<{
  /** Overlay-mode content (the filled list / grid / card). */
  default?: () => unknown;
  /** Extra controls rendered inside the CTA, below the hint. */
  actions?: () => unknown;
}>();

const rootRef = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLInputElement | null>(null);

const { isOverDropZone } = useDropZone(rootRef, {
  onDrop(files) {
    if (props.disabled || !files || files.length === 0) return;
    emit("files", props.multiple ? files : files.slice(0, 1));
  },
  dataTypes: props.dataTypes,
  multiple: props.multiple,
  preventDefaultForUnhandled: true,
});

function open() {
  if (props.disabled) return;
  inputRef.value?.click();
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (files.length > 0) emit("files", files);
}

defineExpose({ open, isOver: isOverDropZone });
</script>

<template>
  <div
    ref="rootRef"
    class="r-dropzone"
    :class="{
      'r-dropzone--active': isOverDropZone && !disabled,
      'r-dropzone--disabled': disabled,
    }"
  >
    <input
      ref="inputRef"
      type="file"
      class="r-dropzone__input"
      :aria-label="inputLabel"
      :accept="accept"
      :multiple="multiple"
      :disabled="disabled"
      @change="onPick"
    />

    <!-- Overlay mode: consumer content + drag-over overlay -->
    <template v-if="overlay">
      <slot />
      <div
        v-show="isOverDropZone && !disabled"
        class="r-dropzone__overlay"
        aria-hidden="true"
      >
        <RIcon :icon="activeIcon" size="36" color="primary" />
        <span v-if="releaseLabel" class="r-dropzone__overlay-label">{{
          releaseLabel
        }}</span>
      </div>
    </template>

    <!-- CTA mode: clickable empty-state dropzone. A `role="button"` div (not
         a <button>) so the optional `actions` slot can host real buttons
         without nesting interactive elements. -->
    <div
      v-else
      class="r-dropzone__cta"
      role="button"
      tabindex="0"
      :aria-disabled="disabled"
      @click="open"
      @keydown.enter.prevent="open"
      @keydown.space.prevent="open"
    >
      <RIcon
        :icon="isOverDropZone ? activeIcon : icon"
        size="44"
        color="primary"
        :class="{ 'r-dropzone__cta-icon--pulse': isOverDropZone && !disabled }"
      />
      <span v-if="activeTitle || title" class="r-dropzone__cta-title">
        {{ isOverDropZone && activeTitle ? activeTitle : title }}
      </span>
      <span v-if="hint" class="r-dropzone__cta-hint">{{ hint }}</span>
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.r-dropzone {
  position: relative;
  border-radius: var(--r-radius-md);
}
/* Disabled dims / blocks only the CTA — in overlay mode the slotted content
   stays fully interactive (drops are no-ops, the overlay never shows). */
.r-dropzone--disabled .r-dropzone__cta {
  opacity: 0.6;
  pointer-events: none;
}

.r-dropzone__input {
  display: none;
}

/* ── CTA mode ─────────────────────────────────────────────────── */
.r-dropzone__cta {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 180px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  appearance: none;
  font: inherit;
  color: var(--r-color-fg);
  border: 2px dashed
    color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  border-radius: var(--r-radius-lg);
  background: var(--r-color-bg-elevated);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-dropzone__cta:hover {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
}
.r-dropzone--active .r-dropzone__cta {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-dropzone__cta-title {
  font-size: 15px;
  font-weight: var(--r-font-weight-semibold);
}
.r-dropzone__cta-hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  max-width: 360px;
  line-height: 1.5;
}
.r-dropzone__cta-icon--pulse {
  animation: r-dropzone-pulse 1.4s ease-in-out infinite;
}
@keyframes r-dropzone-pulse {
  50% {
    transform: scale(1.12);
    filter: drop-shadow(
      0 0 12px color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent)
    );
  }
}

/* ── Overlay mode ─────────────────────────────────────────────── */
.r-dropzone__overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 2px dashed var(--r-color-brand-primary);
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-bg) 78%, transparent);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  pointer-events: none;
}
.r-dropzone__overlay-label {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
</style>
