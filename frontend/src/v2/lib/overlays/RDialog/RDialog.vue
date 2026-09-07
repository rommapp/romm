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
import { createBodyScrollLock, overlayCount } from "../bodyScrollLock";
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
    /** On `sm-and-down`, dock the panel as a full-width bottom sheet
     *  instead of a centred card. Default on — opt out for surfaces that
     *  must stay a compact floating card on phones. */
    fullscreenOnMobile?: boolean;
    /** With the mobile sheet, always fill the full height below the top
     *  navbar (like the full-height user-menu sheet) instead of hugging the
     *  content from the bottom. For tall forms (Match / Edit ROM) that read
     *  better as a stable full-screen surface. Needs `scrollContent` so the
     *  body scrolls internally. Ignored on desktop / when not a sheet. */
    fullHeightOnMobile?: boolean;
  }>(),
  {
    scrollContent: false,
    icon: null,
    width: "auto",
    height: "auto",
    persistent: false,
    fullscreenOnMobile: true,
    fullHeightOnMobile: false,
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

// Shared, reference-counted body scroll lock (see bodyScrollLock.ts).
const { lock: lockBodyScroll, unlock: unlockBodyScroll } =
  createBodyScrollLock();

// Stack depth at the moment this dialog opened (number of overlays
// already open). Drives a per-instance z-index bump so a dialog opened
// from inside another dialog always paints above its parent surface,
// regardless of Teleport mount order. Reset to 0 on close.
const stackDepth = ref(0);
const dialogStyle = computed<Record<string, string> | undefined>(() =>
  stackDepth.value > 0
    ? {
        zIndex: `calc(var(--r-z-dialog, 2400) + ${stackDepth.value * 10})`,
      }
    : undefined,
);

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

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement | null;
      // Snapshot the open-overlay count BEFORE incrementing it via
      // lockBodyScroll(), so the first dialog reads depth 0 and any
      // subsequent dialog sees the previous ones and stacks on top.
      stackDepth.value = overlayCount();
      lockBodyScroll();
      pushEscapable(stackEntry);
      // Defer to the next tick so the panel is mounted before we
      // try to move focus into it. An explicit [autofocus] wins over
      // DOM order; a combined selector list would resolve in document
      // order and always land on the header close button.
      nextTick(() => {
        const focusTarget =
          panelRef.value?.querySelector<HTMLElement>("[autofocus]") ??
          panelRef.value?.querySelector<HTMLElement>(
            "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
          );
        focusTarget?.focus();
      });
    } else {
      unlockBodyScroll();
      popEscapable(stackEntry);
      stackDepth.value = 0;
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
// teardown, route change, or a consumer nulling its `v-if` entity in the
// same tick as `show`), drop our stack entry so the global listener never
// tries to close a destroyed instance, and release the body scroll lock
// the watcher's close branch never got to run.
onBeforeUnmount(() => {
  popEscapable(stackEntry);
  unlockBodyScroll();
});

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
        :class="{
          'r-dialog--fs-mobile': fullscreenOnMobile,
          'r-dialog--full-height': fullHeightOnMobile,
        }"
        role="presentation"
        :style="dialogStyle"
      >
        <!-- Scrim — fades in/out behind the panel. -->
        <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -- scrim is a pointer-only convenience; keyboard closes via Escape through the dialog scope -->
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
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  overflow: hidden;
  color: var(--r-color-fg);
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
}

/* ── Mobile bottom sheet (sm-and-down) ──────────────────────────────
   On phones + small tablets a centred card wastes the screen and a wide
   form gets cramped. Dock the panel to the bottom edge as a full-width
   sheet with a rounded top: small dialogs (confirms) sit content-height
   at the bottom, large ones grow up to `92dvh` and scroll internally.
   `!important` overrides the inline `panelStyle` width/height the
   consumer set for desktop. Selectors hang off `<html>` because RDialog
   teleports outside the app root but `data-bp` lives on `<html>`. */
html[data-bp~="sm-and-down"] .r-dialog--fs-mobile {
  padding: 0;
  align-items: flex-end;
}
html[data-bp~="sm-and-down"] .r-dialog--fs-mobile .r-dialog__panel {
  width: 100vw !important;
  max-width: 100vw !important;
  min-height: 0 !important;
  /* Cap at the space below the top navbar so a tall sheet (Match / Edit ROM)
     never rides up over it — same ceiling the full-height user-menu sheet
     uses. Short dialogs stay content-height; tall ones scroll internally. */
  max-height: calc(100dvh - var(--r-nav-h)) !important;
  border-radius: var(--r-radius-xl) var(--r-radius-xl) 0 0 !important;
  border-bottom: 0 !important;
  padding-bottom: env(safe-area-inset-bottom);
}

/* Full-height variant — pin the sheet to that same ceiling as a fixed height
   (not just a cap) so it fills the screen below the navbar regardless of
   content, overriding any inline `height` the consumer set for desktop. The
   body (with `scrollContent`) scrolls internally. */
html[data-bp~="sm-and-down"]
  .r-dialog--fs-mobile.r-dialog--full-height
  .r-dialog__panel {
  height: calc(100dvh - var(--r-nav-h)) !important;
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
