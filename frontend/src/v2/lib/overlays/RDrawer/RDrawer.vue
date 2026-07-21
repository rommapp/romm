<script setup lang="ts">
// RDrawer — edge-anchored panel that slides in from a side of the
// viewport. Same chrome vocabulary as RDialog (scrim, scroll-lock,
// focus capture, Escape / scrim-click to close) but full-height,
// width-driven, and animated from the side instead of centred.
//
// Slot layout:  header / body / footer
//
// Behaviour:
//   • Escape closes (unless `persistent`).
//   • Click on the scrim closes (unless `persistent`).
//   • Focus moves into the panel on open and restores to the previously
//     focused element on close.
//   • `<body>` gets `overflow: hidden` while open; reference-counted so
//     stacked overlays unlock correctly.
//
// Use cases beyond filters: side info panels (collection / platform /
// firmware drawers when they get migrated), context-driven settings
// flyouts, etc.
import { computed, nextTick, onBeforeUnmount, ref, useSlots, watch } from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "../RDialog/escapeStack.js";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    /** Side the drawer slides in from. */
    side?: "left" | "right";
    /** Pixel width (number → px, string → CSS length). Default 380. */
    width?: number | string;
    /** Block close-on-scrim-click / close-on-Escape. */
    persistent?: boolean;
    /** Leading icon in the header. */
    icon?: string | null;
    /** When true, the body region scrolls; the header / footer stay
     *  pinned. Default true (drawers are rarely short enough to fit). */
    scrollContent?: boolean;
    /** Hide the close button in the header. Use when the drawer is
     *  the only escape (rare). */
    hideClose?: boolean;
  }>(),
  {
    side: "right",
    width: 380,
    persistent: false,
    icon: null,
    scrollContent: true,
    hideClose: false,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "close"): void;
}>();

const slots = useSlots();

const panelRef = ref<HTMLElement | null>(null);
// Element that had focus before the drawer opened — focus returns here
// when the drawer closes so keyboard users don't lose their place.
let previouslyFocused: HTMLElement | null = null;
// Guards this instance so lock/unlock are idempotent
let holdsLock = false;

function closeDrawer() {
  emit("update:modelValue", false);
  emit("close");
}

function onScrimClick() {
  if (props.persistent) return;
  closeDrawer();
}

// Body scroll lock, same reference-count pattern RDialog uses so
// stacking (a Dialog open over a Drawer) unlocks in the right order.
function lockBodyScroll() {
  if (holdsLock) return;
  holdsLock = true;
  const cur = Number(document.body.dataset.rOverlayOpenCount ?? "0") + 1;
  document.body.dataset.rOverlayOpenCount = String(cur);
  if (cur === 1) {
    // Remember whatever overflow was already in effect — a host view may
    // lock the body for its whole lifetime (e.g. the gallery shell, whose
    // only scrollbar is the virtualizer's). Restoring this on unlock
    // instead of forcing "" keeps that lock intact after the drawer closes.
    document.body.dataset.rOverlayPrevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
}
function unlockBodyScroll() {
  if (!holdsLock) return;
  holdsLock = false;
  const cur = Math.max(
    0,
    Number(document.body.dataset.rOverlayOpenCount ?? "0") - 1,
  );
  document.body.dataset.rOverlayOpenCount = String(cur);
  if (cur === 0) {
    document.body.style.overflow =
      document.body.dataset.rOverlayPrevOverflow ?? "";
    delete document.body.dataset.rOverlayPrevOverflow;
  }
}

// Shared escape-stack entry — register on open so a single global
// listener handles Esc across menus, dialogs, drawers, and so
// `useGamepad`'s B-back closes the topmost overlay first. `persistent`
// is read via the getter so toggles while the drawer is open are
// respected.
const escEntry: EscapableEntry = {
  close: () => closeDrawer(),
  get persistent() {
    return props.persistent;
  },
};

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement | null;
      lockBodyScroll();
      pushEscapable(escEntry);
      nextTick(() => {
        const focusTarget = panelRef.value?.querySelector<HTMLElement>(
          "[autofocus], button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
        );
        focusTarget?.focus();
      });
    } else {
      unlockBodyScroll();
      popEscapable(escEntry);
      previouslyFocused?.focus?.();
      previouslyFocused = null;
    }
  },
  { immediate: false },
);

// Safety net — drop the stack entry if we tear down while open (route
// change with the drawer still visible) and release the body scroll lock
// the watcher's close branch never got to run.
onBeforeUnmount(() => {
  popEscapable(escEntry);
  unlockBodyScroll();
});

// ── Width resolution ────────────────────────────────────────────
function asLength(v: number | string): string {
  if (v == null || v === "") return "380px";
  return typeof v === "number" ? `${v}px` : v;
}
const panelStyle = computed(() => ({
  width: asLength(props.width),
  maxWidth: "100vw",
}));

const transitionName = computed(() =>
  props.side === "left" ? "r-drawer-slide-left" : "r-drawer-slide-right",
);
</script>

<template>
  <Teleport to="body">
    <!-- Two transitions wrap the same root: the scrim fades, the panel
         slides. We declare one named transition and let CSS target the
         scrim / panel separately by class. -->
    <Transition :name="transitionName">
      <div
        v-if="modelValue"
        v-bind="$attrs"
        class="r-drawer"
        :class="[`r-drawer--${side}`]"
        role="presentation"
      >
        <!-- Scrim — fades in/out behind the panel. Click closes; the
             keyboard path is the Escape handler on the root, so the
             scrim itself doesn't need a key listener. -->
        <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
        <div class="r-drawer__scrim" @click="onScrimClick" />

        <!-- Panel — receives focus on open. -->
        <div
          ref="panelRef"
          class="r-drawer__panel"
          role="dialog"
          aria-modal="true"
          tabindex="-1"
          :style="panelStyle"
        >
          <!-- Header bar (header slot + optional close button). Hidden
               entirely when no header slot AND `hideClose` is true — a
               drawer with no chrome is sometimes wanted. -->
          <header v-if="slots.header || !hideClose" class="r-drawer__header">
            <RIcon
              v-if="icon"
              :icon="icon"
              size="18"
              class="r-drawer__lead-icon"
            />
            <div class="r-drawer__header-slot">
              <slot name="header" />
            </div>
            <button
              v-if="!hideClose"
              type="button"
              class="r-drawer__close"
              aria-label="Close"
              @click="closeDrawer"
            >
              <RIcon icon="mdi-close" size="16" />
            </button>
          </header>

          <!-- Body — consumer-owned content. -->
          <div
            class="r-drawer__body"
            :class="{ 'r-drawer__body--scroll': scrollContent }"
          >
            <slot />
          </div>

          <!-- Footer bar -->
          <footer v-if="slots.footer" class="r-drawer__footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.r-drawer {
  position: fixed;
  inset: 0;
  z-index: var(--r-z-drawer, 2300);
  display: flex;
  pointer-events: none;
}
.r-drawer--left {
  justify-content: flex-start;
}
.r-drawer--right {
  justify-content: flex-end;
}

.r-drawer__scrim {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--r-color-bg) 70%, transparent);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  pointer-events: auto;
}

.r-drawer__panel {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--r-color-panel);
  border-inline-start: 1px solid var(--r-color-panel-border);
  border-inline-end: 1px solid var(--r-color-panel-border);
  box-shadow:
    0 24px 60px color-mix(in srgb, black 60%, transparent),
    0 4px 20px color-mix(in srgb, black 30%, transparent);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
  pointer-events: auto;
  /* Only the edge that meets the screen gets a border; the screen-edge
     side carries the shadow instead. */
}
.r-drawer--left .r-drawer__panel {
  border-inline-start: 0;
}
.r-drawer--right .r-drawer__panel {
  border-inline-end: 0;
}

/* On phones the drawer goes full-screen — there's a close button in the
   header, so the slim tap-to-dismiss scrim strip isn't needed and the
   extra width is more useful. `!important` beats the inline `panelStyle`
   width the consumer set for desktop. Selector hangs off `<html>` —
   RDrawer teleports outside the app root but `data-bp` lives there. */
html[data-bp~="xs"] .r-drawer__panel {
  width: 100vw !important;
  max-width: 100vw !important;
}

/* ── Header ────────────────────────────────────────────────────── */
.r-drawer__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-drawer__lead-icon {
  color: var(--r-color-fg-secondary);
  flex-shrink: 0;
}
.r-drawer__header-slot {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-drawer__close {
  appearance: none;
  background: transparent;
  border: 0;
  border-radius: 6px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1);
}
.r-drawer__close:hover {
  background: color-mix(in srgb, var(--r-color-fg) 10%, transparent);
  color: var(--r-color-fg);
}
.r-drawer__close:active {
  transform: scale(0.92);
}

/* ── Body ──────────────────────────────────────────────────────── */
.r-drawer__body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 14px;
}
.r-drawer__body--scroll {
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-drawer__body--scroll::-webkit-scrollbar {
  width: 8px;
}
.r-drawer__body--scroll::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 4px;
}

/* ── Footer ────────────────────────────────────────────────────── */
.r-drawer__footer {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--r-color-border);
}

/* ── Open / close motion ──────────────────────────────────────── */
/* Right-anchored: panel slides in from the right; scrim fades. */
.r-drawer-slide-right-enter-active .r-drawer__scrim,
.r-drawer-slide-right-leave-active .r-drawer__scrim,
.r-drawer-slide-left-enter-active .r-drawer__scrim,
.r-drawer-slide-left-leave-active .r-drawer__scrim {
  transition: opacity 200ms var(--r-motion-ease-out);
}
.r-drawer-slide-right-enter-active .r-drawer__panel,
.r-drawer-slide-right-leave-active .r-drawer__panel,
.r-drawer-slide-left-enter-active .r-drawer__panel,
.r-drawer-slide-left-leave-active .r-drawer__panel {
  transition: transform 260ms cubic-bezier(0.32, 0.72, 0.24, 1);
}
.r-drawer-slide-right-enter-from .r-drawer__scrim,
.r-drawer-slide-right-leave-to .r-drawer__scrim,
.r-drawer-slide-left-enter-from .r-drawer__scrim,
.r-drawer-slide-left-leave-to .r-drawer__scrim {
  opacity: 0;
}
.r-drawer-slide-right-enter-from .r-drawer__panel,
.r-drawer-slide-right-leave-to .r-drawer__panel {
  transform: translateX(100%);
}
.r-drawer-slide-left-enter-from .r-drawer__panel,
.r-drawer-slide-left-leave-to .r-drawer__panel {
  transform: translateX(-100%);
}

@media (prefers-reduced-motion: reduce) {
  .r-drawer-slide-right-enter-active .r-drawer__panel,
  .r-drawer-slide-right-leave-active .r-drawer__panel,
  .r-drawer-slide-left-enter-active .r-drawer__panel,
  .r-drawer-slide-left-leave-active .r-drawer__panel {
    transition: none;
  }
}
</style>
