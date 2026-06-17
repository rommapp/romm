<script setup lang="ts">
// RTooltip — positioned with `@floating-ui/vue` (the only standalone
// dep we lean on here — battle-tested overlay math with flip / shift /
// offset / arrow middleware). The surface itself matches the v2 glass
// language (near-black bg, subtle border, blur), driven by tokens.
//
// Two activator patterns:
//
//   1. Slot (most flexible):
//      <RTooltip text="Save">
//        <template #activator="{ props }">
//          <RBtn v-bind="props" icon="mdi-content-save" />
//        </template>
//      </RTooltip>
//
//      `props` carries the event handlers (mouseenter/leave, focus/blur),
//      so the activator gets pointer + keyboard reveal for free.
//
//   2. Parent-attach (no extra markup):
//      <button>
//        <RTooltip activator="parent" text="Save" />
//      </button>
//
//      RTooltip wires the listeners onto `$el.parentElement` itself.
//      Used inside primitives that already have their own root
//      element (RPlatformIcon, MissingFSBadge, …).
//
// Open / close motion mirrors the rest of the lib — a short fade +
// subtle scale-up from 0.96, with reduced-motion stripping the scale.
// `prefers-reduced-motion` users keep the fade.
import {
  arrow,
  autoUpdate,
  flip,
  offset as offsetMiddleware,
  shift,
  useFloating,
} from "@floating-ui/vue";
import type { Placement } from "@floating-ui/vue";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  useSlots,
  watch,
} from "vue";

defineOptions({ inheritAttrs: false });

// Anchor strings ("top", "bottom start", …) — translated to
// floating-ui's placement vocabulary at compute time.
type Anchor =
  | "top"
  | "bottom"
  | "start"
  | "end"
  | "top start"
  | "top end"
  | "bottom start"
  | "bottom end"
  | "start top"
  | "start bottom"
  | "end top"
  | "end bottom";

interface Props {
  text?: string;
  /** Anchor; mapped to floating-ui placement internally. */
  location?: Anchor;
  openDelay?: number | string;
  closeDelay?: number | string;
  /** Controlled visibility (uncontrolled when undefined). */
  modelValue?: boolean;
  contentClass?: string;
  /** Px gap between activator and tooltip body. */
  offset?: number | string;
  /** "parent" — attach to the immediate parent element of <RTooltip>. */
  activator?: "parent";
  /** Hide entirely (useful with `v-if` style guards on conditional tooltips). */
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  text: undefined,
  location: "top",
  openDelay: 300,
  closeDelay: 0,
  modelValue: undefined,
  contentClass: undefined,
  offset: 6,
  activator: undefined,
  disabled: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const slots = useSlots();

// ── Placement translation ───────────────────────────────────────
const PLACEMENT_MAP: Record<Anchor, Placement> = {
  top: "top",
  bottom: "bottom",
  start: "left",
  end: "right",
  "top start": "top-start",
  "top end": "top-end",
  "bottom start": "bottom-start",
  "bottom end": "bottom-end",
  "start top": "left-start",
  "start bottom": "left-end",
  "end top": "right-start",
  "end bottom": "right-end",
};
const placement = computed<Placement>(
  () => PLACEMENT_MAP[props.location] ?? "bottom",
);

const offsetPx = computed<number>(() => Number(props.offset) || 0);

// ── Open state ──────────────────────────────────────────────────
// `internalOpen` carries the uncontrolled state. When `modelValue` is
// passed we mirror it; emitted `update:modelValue` keeps the parent
// in sync. Same idiom as the rest of the lib (RDialog, RMenu).
const internalOpen = ref(false);
const isOpen = computed(() =>
  props.modelValue !== undefined ? !!props.modelValue : internalOpen.value,
);
function setOpen(v: boolean) {
  if (props.modelValue !== undefined) {
    emit("update:modelValue", v);
  } else {
    internalOpen.value = v;
  }
}

// Cancellable timers so hover-flicker doesn't open/close repeatedly.
let openTimer: number | null = null;
let closeTimer: number | null = null;
function clearTimers() {
  if (openTimer !== null) {
    clearTimeout(openTimer);
    openTimer = null;
  }
  if (closeTimer !== null) {
    clearTimeout(closeTimer);
    closeTimer = null;
  }
}
function show() {
  if (props.disabled || !hasContent.value) return;
  clearTimers();
  const d = Number(props.openDelay) || 0;
  if (d <= 0) {
    setOpen(true);
  } else {
    openTimer = window.setTimeout(() => setOpen(true), d);
  }
}
function hide() {
  clearTimers();
  const d = Number(props.closeDelay) || 0;
  if (d <= 0) {
    setOpen(false);
  } else {
    closeTimer = window.setTimeout(() => setOpen(false), d);
  }
}

const hasContent = computed(() => !!(props.text || slots.default));

// ── Floating-ui refs ────────────────────────────────────────────
const reference = ref<Element | null>(null);
const floating = ref<HTMLElement | null>(null);
const arrowEl = ref<HTMLElement | null>(null);

const {
  floatingStyles,
  middlewareData,
  placement: activePlacement,
} = useFloating(reference, floating, {
  placement,
  strategy: "fixed",
  open: isOpen,
  // Use top/left positioning instead of `transform: translate(x, y)` —
  // otherwise the enter-transition's `transform: scale(...)` clobbers
  // floating-ui's translate and the tooltip visibly slides from (0, 0)
  // to its target spot. With `transform: false`, `transform` is free
  // for the scale-up animation.
  transform: false,
  whileElementsMounted: autoUpdate,
  middleware: computed(() => [
    offsetMiddleware(offsetPx.value),
    flip({ padding: 8 }),
    shift({ padding: 8 }),
    arrow({ element: arrowEl, padding: 6 }),
  ]),
});

// Arrow inline positioning — floating-ui only computes the offset
// along the perpendicular axis; we anchor it to the opposite side of
// the active placement so it always points at the reference.
const arrowStyle = computed<Record<string, string>>(() => {
  const data = middlewareData.value.arrow;
  if (!data) return {};
  const side = activePlacement.value.split("-")[0] as
    | "top"
    | "right"
    | "bottom"
    | "left";
  const staticSide = {
    top: "bottom",
    right: "left",
    bottom: "top",
    left: "right",
  }[side];
  const style: Record<string, string> = {};
  if (data.x != null) style.left = `${data.x}px`;
  if (data.y != null) style.top = `${data.y}px`;
  // Pull the arrow square half-out so the rotated corner sits on the
  // tooltip's edge instead of inside the body.
  style[staticSide] = "-4px";
  return style;
});

// ── Activator wiring ────────────────────────────────────────────
// For the slot pattern we hand back a `props` object the activator
// spreads on itself. The events are Vue-style ("onMouseenter", …) so
// they bind correctly when used via `v-bind`.
const activatorProps = computed(() => ({
  onMouseenter: show,
  onMouseleave: hide,
  onFocus: show,
  onBlur: hide,
}));

// For the parent-attach pattern we sit silently in the parent's DOM
// and register listeners on `$el.parentElement` at mount. We deliberately
// use a comment node as `$el` so the tooltip itself doesn't take up
// flow space inside the parent.
const root = ref<HTMLElement | null>(null);
function attachToParent() {
  if (props.activator !== "parent") return;
  const parent = root.value?.parentElement;
  if (!parent) return;
  reference.value = parent;
  parent.addEventListener("mouseenter", show);
  parent.addEventListener("mouseleave", hide);
  parent.addEventListener("focusin", show);
  parent.addEventListener("focusout", hide);
}
function detachFromParent() {
  if (props.activator !== "parent") return;
  const parent = root.value?.parentElement;
  if (!parent) return;
  parent.removeEventListener("mouseenter", show);
  parent.removeEventListener("mouseleave", hide);
  parent.removeEventListener("focusin", show);
  parent.removeEventListener("focusout", hide);
}

onMounted(() => {
  // For the slot pattern, the reference is the first child rendered
  // by the slot — we read it from the wrapper span on mount.
  if (props.activator !== "parent") {
    reference.value = activatorWrapper.value?.firstElementChild ?? null;
  } else {
    attachToParent();
  }
});
onBeforeUnmount(() => {
  detachFromParent();
  clearTimers();
});

// ── Slot activator wrapper ──────────────────────────────────────
// We render a `display: contents` span around the activator slot so
// we have a stable DOM handle for `firstElementChild` without
// disturbing layout.
const activatorWrapper = ref<HTMLElement | null>(null);

// Re-read the reference if the slot content changes (e.g., v-if flips).
watch(
  () => slots.activator,
  () => {
    if (props.activator !== "parent") {
      reference.value = activatorWrapper.value?.firstElementChild ?? null;
    }
  },
);

// Side bucket — used by the open animation to grow the tooltip out of
// the activator (transform-origin + a tiny "from" translate from that
// side, so the bloom reads as kinetic instead of a flat scale-up).
const sideClass = computed(() => {
  const side = activePlacement.value.split("-")[0];
  return `r-tooltip--side-${side}`;
});

const tooltipClasses = computed(() =>
  ["r-tooltip", sideClass.value, props.contentClass].filter(Boolean).join(" "),
);
</script>

<template>
  <!-- Parent-attach: we don't render an activator wrapper; we only
       leave a placeholder so we have a $el to read parentElement
       from. The tooltip body is still teleported below. -->
  <template v-if="activator === 'parent'">
    <span
      ref="root"
      class="r-tooltip-anchor"
      aria-hidden="true"
      style="display: none"
    />
  </template>
  <!-- Slot activator: render the user's element. `display: contents`
       keeps the wrapper out of the layout. -->
  <span
    v-else
    ref="activatorWrapper"
    class="r-tooltip-activator"
    style="display: contents"
  >
    <slot name="activator" :props="activatorProps" />
  </span>

  <!-- Tooltip body — teleported to <body> so it escapes overflow
       contexts and z-index stacking. Mount only when open to avoid
       paying for layout on every hidden tooltip in the page. -->
  <Teleport to="body">
    <Transition name="r-tooltip-fade">
      <div
        v-if="isOpen && hasContent && !disabled"
        ref="floating"
        v-bind="$attrs"
        :class="tooltipClasses"
        :style="floatingStyles"
        role="tooltip"
      >
        <slot>{{ text }}</slot>
        <span
          ref="arrowEl"
          class="r-tooltip__arrow"
          :style="arrowStyle"
          aria-hidden="true"
        />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.r-tooltip {
  /* Surface inherits from the global `r-tooltip` skin in global.css
     for theme alignment. Re-declare here so the primitive is
     self-contained — scoped tokens win when both stylesheets load. */
  position: fixed;
  z-index: var(--r-z-tooltip, 2600);
  background: var(--r-color-tooltip-bg);
  border: 1px solid var(--r-color-tooltip-border);
  border-radius: 6px;
  color: var(--r-color-fg);
  font-size: 11.5px;
  font-weight: 500;
  line-height: 1.4;
  letter-spacing: 0.01em;
  padding: 5px 10px;
  max-width: 280px;
  box-shadow:
    0 4px 14px color-mix(in srgb, black 45%, transparent),
    0 1px 2px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  pointer-events: none;
}

/* Arrow — small square rotated 45deg into a diamond. Only the two
   borders facing the activator are painted, so it reads as a folded
   corner of the surface. Which two borders that is depends on the
   active placement — the parent's `--side-*` class flips the right
   pair. */
.r-tooltip__arrow {
  position: absolute;
  width: 8px;
  height: 8px;
  background: var(--r-color-tooltip-bg);
  transform: rotate(45deg);
  pointer-events: none;
}
/* Tooltip above the activator → arrow at the bottom → bottom-right
   pair of borders ends up pointing down after the rotation. */
.r-tooltip--side-top .r-tooltip__arrow {
  border-right: 1px solid var(--r-color-tooltip-border);
  border-bottom: 1px solid var(--r-color-tooltip-border);
}
/* Tooltip below → arrow at the top → top-left pair points up. */
.r-tooltip--side-bottom .r-tooltip__arrow {
  border-top: 1px solid var(--r-color-tooltip-border);
  border-left: 1px solid var(--r-color-tooltip-border);
}
/* Tooltip on the left → arrow at the right → top-right pair points
   right. */
.r-tooltip--side-left .r-tooltip__arrow {
  border-top: 1px solid var(--r-color-tooltip-border);
  border-right: 1px solid var(--r-color-tooltip-border);
}
/* Tooltip on the right → arrow at the left → bottom-left pair points
   left. */
.r-tooltip--side-right .r-tooltip__arrow {
  border-bottom: 1px solid var(--r-color-tooltip-border);
  border-left: 1px solid var(--r-color-tooltip-border);
}

/* Open / close motion. The tooltip "blooms" out of the activator —
   `transform-origin` anchors to the side facing the activator, and a
   tiny initial translate (away from the activator) means the bloom
   reads as a quick spring rather than a flat scale-up. Numbers tuned
   so the overshoot is felt (10–15 % past 1.0) without wobbling on
   slower hardware. */
.r-tooltip {
  --r-tt-tx: 0;
  --r-tt-ty: 0;
  transform-origin: center;
}
.r-tooltip--side-top {
  /* Tooltip sits above the activator — grow downward toward it. */
  transform-origin: center bottom;
  --r-tt-ty: 6px;
}
.r-tooltip--side-bottom {
  /* Tooltip sits below the activator — grow downward away from it. */
  transform-origin: center top;
  --r-tt-ty: -6px;
}
.r-tooltip--side-left {
  transform-origin: right center;
  --r-tt-tx: 6px;
}
.r-tooltip--side-right {
  transform-origin: left center;
  --r-tt-tx: -6px;
}

.r-tooltip-fade-enter-from {
  opacity: 0;
  transform: translate(var(--r-tt-tx), var(--r-tt-ty)) scale(0.7);
}
.r-tooltip-fade-leave-to {
  opacity: 0;
  /* Leave shrinks back into the activator without the slide — quick &
     unobtrusive, the hover-out side of the interaction. */
  transform: scale(0.92);
}
.r-tooltip-fade-enter-active {
  /* Spring overshoot on transform — same easing the rest of the lib's
     "appears" use (RSwitch thumb, RCheckbox icon). Slightly longer than
     opacity so the bounce keeps reading after the fade settles. */
  transition:
    opacity 140ms var(--r-motion-ease-out),
    transform 320ms cubic-bezier(0.34, 1.7, 0.55, 1);
}
.r-tooltip-fade-leave-active {
  transition:
    opacity 110ms var(--r-motion-ease-in),
    transform 110ms var(--r-motion-ease-in);
}

/* Arrow follows the surface — wrap it in its own fade so it doesn't
   pop in late after the body has finished scaling. The slight delay
   means the surface's bloom lands first, then the tip "catches up". */
.r-tooltip-fade-enter-active .r-tooltip__arrow {
  animation: r-tooltip-arrow-in 220ms var(--r-motion-ease-out) 60ms backwards;
}
@keyframes r-tooltip-arrow-in {
  from {
    opacity: 0;
    transform: rotate(45deg) scale(0.4);
  }
  to {
    opacity: 1;
    transform: rotate(45deg) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-tooltip-fade-enter-from,
  .r-tooltip-fade-leave-to {
    transform: none;
  }
  .r-tooltip-fade-enter-active,
  .r-tooltip-fade-leave-active {
    transition: opacity 100ms linear;
  }
  .r-tooltip-fade-enter-active .r-tooltip__arrow {
    animation: none;
  }
}
</style>
