<script setup lang="ts">
// RDialog — teleports to <body>, paints a scrim + glass panel, and
// locks page scroll while open. Slot layout: header / toolbar /
// content / append / footer.
//
// Behaviour:
//   • Escape closes (unless `persistent`).
//   • Click on the scrim closes (unless `persistent`).
//   • Focus moves into the dialog on open and restores to the previously
//     focused element on close.
//   • `<body>` gets `overflow: hidden` while any dialog is open; we use
//     a reference count so nested dialogs unlock correctly.
//
// The primitive owns surface + chrome only. Loading spinners, empty
// states, "no results" messaging and any other app-driven content
// belong inside the consumer's `#content` slot — composed from
// REmptyState / RProgressCircular / RSpinner as needed.
import { computed, nextTick, ref, useSlots, watch } from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    scrollContent?: boolean;
    icon?: string | null;
    width?: number | string;
    height?: number | string;
    /** Block close-on-scrim-click / close-on-Escape. */
    persistent?: boolean;
  }>(),
  {
    scrollContent: false,
    icon: null,
    width: "auto",
    height: "auto",
    persistent: false,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "close"): void;
}>();

const slots = useSlots();

const panelRef = ref<HTMLElement | null>(null);
// Element that had focus before the dialog opened — focus returns here
// when the dialog closes so keyboard users don't lose their place.
let previouslyFocused: HTMLElement | null = null;

function closeDialog() {
  emit("update:modelValue", false);
  emit("close");
}

function onScrimClick() {
  if (props.persistent) return;
  closeDialog();
}

function onKeyDown(evt: KeyboardEvent) {
  if (evt.key === "Escape" && !props.persistent) {
    evt.stopPropagation();
    closeDialog();
  }
}

// ── Body scroll lock — reference-counted so nested dialogs unlock
// correctly when the outer one is still open. ─────────────────────
function lockBodyScroll() {
  const cur = Number(document.body.dataset.rDialogOpenCount ?? "0") + 1;
  document.body.dataset.rDialogOpenCount = String(cur);
  if (cur === 1) {
    document.body.style.overflow = "hidden";
  }
}
function unlockBodyScroll() {
  const cur = Math.max(
    0,
    Number(document.body.dataset.rDialogOpenCount ?? "0") - 1,
  );
  document.body.dataset.rDialogOpenCount = String(cur);
  if (cur === 0) {
    document.body.style.overflow = "";
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement | null;
      lockBodyScroll();
      // Defer to the next tick so the panel is mounted before we
      // try to move focus into it.
      nextTick(() => {
        const focusTarget = panelRef.value?.querySelector<HTMLElement>(
          "[autofocus], button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
        );
        focusTarget?.focus();
      });
    } else {
      unlockBodyScroll();
      // Restore focus to the element that opened the dialog.
      previouslyFocused?.focus?.();
      previouslyFocused = null;
    }
  },
  { immediate: false },
);

// ── Width / height resolution ───────────────────────────────────
function asLength(v: number | string): string | undefined {
  if (v == null || v === "" || v === "auto") return undefined;
  return typeof v === "number" ? `${v}px` : v;
}
const panelStyle = computed(() => {
  const h = asLength(props.height);
  const w = asLength(props.width);
  return {
    width: w,
    maxWidth: w,
    minHeight: h,
    maxHeight: h,
  };
});
</script>

<template>
  <Teleport to="body">
    <!-- Auto-detect mode: Vue reads the longest CSS transition
         declared on the root (`.r-dialog`'s opacity) and unmounts when
         that transitionend fires. The panel scales alongside via its
         own always-on transform transition. -->
    <Transition name="r-dialog-fade">
      <div
        v-if="modelValue"
        v-bind="$attrs"
        class="r-dialog"
        role="presentation"
        @keydown="onKeyDown"
      >
        <!-- Scrim — fades in/out behind the panel. -->
        <div class="r-dialog__scrim" @click="onScrimClick" />

        <!-- Panel — receives focus on open. -->
        <div
          ref="panelRef"
          class="r-dialog__panel"
          role="dialog"
          aria-modal="true"
          tabindex="-1"
          :style="panelStyle"
        >
          <!-- Header bar -->
          <header class="r-dialog__header">
            <RIcon
              v-if="icon"
              :icon="icon"
              size="18"
              class="r-dialog__lead-icon"
            />
            <div class="r-dialog__header-slot">
              <slot name="header" />
            </div>
            <button
              type="button"
              class="r-dialog__close"
              aria-label="Close"
              @click="closeDialog"
            >
              <RIcon icon="mdi-close" size="16" />
            </button>
          </header>

          <!-- Optional secondary toolbar -->
          <div v-if="slots.toolbar" class="r-dialog__toolbar">
            <slot name="toolbar" />
          </div>

          <!-- Body — content is the consumer's responsibility (loading,
               empty, results, forms, …). The primitive just provides the
               padded, optionally-scrollable region. -->
          <div
            class="r-dialog__body"
            :class="{ 'r-dialog__body--scroll': scrollContent }"
          >
            <slot name="content" />
          </div>

          <!-- Append -->
          <div v-if="slots.append" class="r-dialog__append">
            <slot name="append" />
          </div>

          <!-- Footer bar -->
          <footer v-if="slots.footer" class="r-dialog__footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Full-viewport container — flexbox centres the panel. No always-on
   transition: the opacity animation is scoped to `enter-active` only,
   so Vue's `<Transition>` doesn't wait for a phantom transitionend on
   close. */
.r-dialog {
  position: fixed;
  inset: 0;
  z-index: var(--r-z-dialog, 2400);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.r-dialog__scrim {
  position: absolute;
  inset: 0;
  background: var(--r-color-overlay-scrim-soft);
  /* Pointer events live here; the panel is layered above. */
}

.r-dialog__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: var(--r-radius-card);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  overflow: hidden;
  color: var(--r-color-fg);
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
}

/* ── Header ─────────────────────────────────────────────────────── */
.r-dialog__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 10px 12px 16px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-dialog__lead-icon {
  flex-shrink: 0;
  color: var(--r-color-fg-secondary);
}
.r-dialog__header-slot {
  flex: 1;
  min-width: 0;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-dialog__close {
  appearance: none;
  background: transparent;
  border: 0;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-dialog__close:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Toolbar / append / footer ────────────────────────────────── */
.r-dialog__toolbar {
  padding: 8px 14px;
  background: var(--r-color-bg-elevated);
  border-bottom: 1px solid var(--r-color-border);
}
.r-dialog__append {
  padding: 0;
}
.r-dialog__body {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  /* Symmetric padding so default content reads in a comfortable box. */
  padding: 18px 16px;
}
.r-dialog__body--scroll {
  overflow-y: auto;
  scrollbar-width: thin;
}
.r-dialog__footer {
  padding: 10px 14px;
  border-top: 1px solid var(--r-color-border);
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Open motion only ────────────────────────────────────────
   The dialog blooms in (root fades from 0, panel springs from 0.94
   scale). Close is intentionally instant — no `leave-*` rules and no
   always-on transition means Vue unmounts on the same frame. */
.r-dialog-fade-enter-from {
  opacity: 0;
}
.r-dialog-fade-enter-from .r-dialog__panel {
  transform: scale(0.94);
}
.r-dialog-fade-enter-active {
  transition: opacity 220ms var(--r-motion-ease-out);
}
.r-dialog-fade-enter-active .r-dialog__panel {
  transition: transform 280ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

@media (prefers-reduced-motion: reduce) {
  .r-dialog-fade-enter-active,
  .r-dialog-fade-enter-active .r-dialog__panel {
    transition: opacity 120ms linear;
  }
  .r-dialog-fade-enter-from .r-dialog__panel {
    transform: none;
  }
}
</style>
