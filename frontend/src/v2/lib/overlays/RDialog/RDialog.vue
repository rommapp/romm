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
import { computed, nextTick, onBeforeUnmount, ref, useSlots, watch } from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "./escapeStack";

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

// Per-instance entry on the shared escape stack — registered when
// `modelValue` flips to true, removed when it flips to false (or on
// unmount). `persistent` is read via the getter so the global listener
// always sees the current value (the user could toggle it while the
// dialog is open).
const stackEntry: EscapableEntry = {
  close: () => closeDialog(),
  get persistent() {
    return props.persistent;
  },
};

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
      pushEscapable(stackEntry);
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
      popEscapable(stackEntry);
      // Restore focus to the element that opened the dialog.
      previouslyFocused?.focus?.();
      previouslyFocused = null;
    }
  },
  // `immediate: true` so dialogs that mount already open (e.g. when a
  // consumer wraps RDialog in `v-if="entity"` and flips both `entity`
  // and `show` in the same tick — EditRomDialog, ManageCollectionsDialog,
  // …) still register on the escape stack. Without this the watch
  // never sees the initial `true` and Esc silently does nothing.
  { immediate: true },
);

// Safety net — if the component unmounts while still open (parent
// teardown, route change), drop our stack entry so the global listener
// never tries to close a destroyed instance.
onBeforeUnmount(() => popEscapable(stackEntry));

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
         own always-on transform transition.
         `appear` makes the enter animation fire on the dialog's first
         mount too — consumers that gate RDialog with `v-if="entity"`
         outside (EditRomDialog, EditUserDialog) flip the entity ref
         AND `show` in the same tick, so without `appear` the dialog
         mounts already-open and Vue sees no v-if transition. With it,
         the bloom happens either way: initial-mount-with-true or a
         subsequent false → true flip on a steady-mounted dialog. -->
    <Transition name="r-dialog-fade" appear>
      <div
        v-if="modelValue"
        v-bind="$attrs"
        class="r-dialog"
        role="presentation"
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
  /* `flex: 1 1 auto` rather than `1 1 0` so the body's natural content
     size is used when no explicit panel height is set (auto-height
     dialogs sized to their content). With `basis: 0` the body would
     collapse and the panel's `overflow: hidden` would clip everything
     below the header/toolbar/footer. When the panel has a fixed height
     the leftover space still flows here via `flex-grow: 1`, so the
     footer stays pinned at the bottom. */
  flex: 1 1 auto;
  min-height: 0;
  /* Padding + gap are owned here so consumers don't have to re-declare
     a `__body` wrapper just to space their fields. Override at the
     consumer end only when the layout genuinely differs (grids, hero
     rows, centred icon stacks). */
  padding: 20px 24px;
  gap: 14px;
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
