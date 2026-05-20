<script setup lang="ts">
// RBtn — the workhorse of the v2 library.
//
// Polymorphic root via `<component :is>`:
//   • `to` set → renders RouterLink
//   • `href` set → renders <a>
//   • otherwise → renders <button>
// So call sites that use `to="/foo"` or `href="https://…"` work as
// drop-in router/anchor variants.
//
// Variants `flat / elevated / translucent / outlined / text / plain`
// — same shape across the lib. `border` adds a translucent
// currentColor border on top of any variant (used to recreate the
// RTag chip activator look). `block` stretches to 100% width.
//
// `icon` accepts a string (MDI class) or `true`. When set, the button
// collapses to a square hit target (width = height). Pair with
// `prepend-icon` / `append-icon` to get icon + label without icon-only
// styling.
//
// `loading` swaps the content for an inline spinner. The flip is
// debounced by `loadingDebounce` (default 200ms) so quick actions
// don't paint a spinner-flash; the hide step is immediate.
//
// Hover / active feedback comes from a `::before` overlay tinted by
// `currentColor` so all six variants share the same vocabulary —
// no per-variant `:hover` rules. Activation paints a circular ripple
// expanding from the input point inside a clip wrapper so it never
// escapes the rounded silhouette nor masks the elevated shadow.
import { computed, onBeforeUnmount, ref, useSlots, watch } from "vue";
import { RouterLink, type RouteLocationRaw } from "vue-router";
import RIcon from "../RIcon/RIcon.vue";
import RProgressCircular from "../RProgressCircular/RProgressCircular.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  variant?: "flat" | "text" | "elevated" | "translucent" | "outlined" | "plain";
  color?: string;
  rounded?: string | number | boolean;
  loading?: boolean;
  /** ms before the spinner appears after `loading` flips true. */
  loadingDebounce?: number;
  disabled?: boolean;
  block?: boolean;
  size?: "x-small" | "small" | "default" | "large" | "x-large";
  density?: "default" | "comfortable" | "compact";
  /** `true` → square icon-only button. `string` → MDI icon rendered as
   *  the button's sole content (icon-only). */
  icon?: string | boolean;
  prependIcon?: string;
  appendIcon?: string;
  type?: "button" | "submit" | "reset";
  /** Translucent currentColor border on top of the chosen variant. */
  border?: boolean;
  /** Paints the lib's `--r-color-bg-elevated` token behind the button.
   *  Composes with any variant — use it when the button needs to read
   *  as "raised on a tinted pill" rather than "transparent on the page",
   *  so it visually aligns with adjacent segmented `RSliderBtnGroup`
   *  surfaces (e.g., toolbar icon buttons next to sliders). */
  surface?: boolean;
  /** Renders the button as a router-link to this route. */
  to?: RouteLocationRaw;
  /** Renders the button as an `<a>` href. */
  href?: string;
  /** Target for `<a>` mode. */
  target?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "flat",
  color: undefined,
  rounded: "md",
  loading: false,
  loadingDebounce: 200,
  disabled: false,
  block: false,
  size: "default",
  density: "default",
  icon: undefined,
  prependIcon: undefined,
  appendIcon: undefined,
  type: "button",
  border: false,
  surface: false,
  to: undefined,
  href: undefined,
  target: undefined,
});

const slots = useSlots();

// ── Polymorphic root ─────────────────────────────────────────────
const elementType = computed(() => {
  if (props.to !== undefined && props.to !== null) return RouterLink;
  if (props.href !== undefined && props.href !== null) return "a";
  return "button";
});

const dynamicAttrs = computed<Record<string, unknown>>(() => {
  // For `<a>` and RouterLink, `disabled` isn't a real HTML attribute —
  // we apply aria-disabled + pointer-events: none via CSS. For
  // <button>, the native `disabled` attribute is the right tool.
  if (props.to !== undefined && props.to !== null) {
    return {
      to: props.to,
      ariaDisabled: props.disabled ? "true" : undefined,
    };
  }
  if (props.href !== undefined && props.href !== null) {
    return {
      // Strip the href entirely when disabled so keyboard activation
      // doesn't fire — links can't be `disabled` natively.
      href: props.disabled ? undefined : props.href,
      target: props.target,
      ariaDisabled: props.disabled ? "true" : undefined,
    };
  }
  return {
    type: props.type,
    disabled: props.disabled,
  };
});

// ── Tone resolver ────────────────────────────────────────────────
const TONE_MAP: Record<string, string> = {
  primary: "var(--r-color-brand-primary)",
  secondary: "var(--r-color-brand-secondary)",
  accent: "var(--r-color-brand-accent)",
  success: "var(--r-color-success)",
  warning: "var(--r-color-warning)",
  danger: "var(--r-color-danger)",
  error: "var(--r-color-danger)",
  info: "var(--r-color-info)",
  "romm-red": "var(--r-color-romm-red)",
  "romm-green": "var(--r-color-romm-green)",
  "romm-blue": "var(--r-color-romm-blue)",
  "romm-gold": "var(--r-color-romm-gold)",
};
const resolvedColor = computed<string | undefined>(() => {
  const c = props.color;
  if (!c) return undefined;
  return TONE_MAP[c] ?? c;
});

// ── Rounded resolver ─────────────────────────────────────────────
const ROUNDED_MAP: Record<string, string> = {
  "0": "0",
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "999px",
  pill: "999px",
  circle: "50%",
};
const resolvedRounded = computed<string>(() => {
  const r = props.rounded;
  if (r === undefined || r === null || r === "") return "8px";
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

// ── Icon-only detection ──────────────────────────────────────────
const iconString = computed<string | undefined>(() =>
  typeof props.icon === "string" ? props.icon : undefined,
);
const isIconBtn = computed(
  () =>
    props.icon === true ||
    (typeof props.icon === "string" && props.icon.length > 0),
);

// ── Debounced loading ────────────────────────────────────────────
const debouncedLoading = ref(false);
let pendingTimer: ReturnType<typeof setTimeout> | null = null;

function clearTimer() {
  if (pendingTimer) {
    clearTimeout(pendingTimer);
    pendingTimer = null;
  }
}

watch(
  () => props.loading,
  (next) => {
    clearTimer();
    if (!next) {
      debouncedLoading.value = false;
      return;
    }
    if (props.loadingDebounce <= 0) {
      debouncedLoading.value = true;
      return;
    }
    pendingTimer = setTimeout(() => {
      debouncedLoading.value = true;
      pendingTimer = null;
    }, props.loadingDebounce);
  },
  { immediate: true },
);

onBeforeUnmount(clearTimer);

// ── Ripple ───────────────────────────────────────────────────────
// A circular wave expands from the activation point. Pointer events
// give us coordinates; keyboard activation falls back to the centre.
const rippleContainer = ref<HTMLElement | null>(null);

function spawnRipple(originX?: number, originY?: number) {
  const container = rippleContainer.value;
  if (!container || props.disabled || props.loading) return;
  const rect = container.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  const cx = originX ?? rect.left + rect.width / 2;
  const cy = originY ?? rect.top + rect.height / 2;
  // Diameter = 2× longest distance from origin to a corner, so the
  // wave always reaches the farthest edge regardless of click point.
  const dx = Math.max(cx - rect.left, rect.right - cx);
  const dy = Math.max(cy - rect.top, rect.bottom - cy);
  const size = Math.hypot(dx, dy) * 2;
  const ripple = document.createElement("span");
  ripple.className = "r-btn__ripple";
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${cx - rect.left - size / 2}px`;
  ripple.style.top = `${cy - rect.top - size / 2}px`;
  container.appendChild(ripple);
  ripple.addEventListener("animationend", () => ripple.remove(), {
    once: true,
  });
}

function onPointerDown(e: PointerEvent) {
  spawnRipple(e.clientX, e.clientY);
}

function onKeyDown(e: KeyboardEvent) {
  if (e.repeat) return;
  if (e.key === "Enter" || e.key === " ") spawnRipple();
}

// Spinner size scales with the button — readable across the ladder.
const spinnerSize = computed(() => {
  switch (props.size) {
    case "x-small":
      return 12;
    case "small":
      return 14;
    case "large":
      return 18;
    case "x-large":
      return 20;
    default:
      return 16;
  }
});
</script>

<template>
  <component
    :is="elementType"
    v-bind="{ ...$attrs, ...dynamicAttrs }"
    class="r-btn"
    :class="[
      `r-btn--${variant}`,
      `r-btn--${size}`,
      `r-btn--density-${density}`,
      {
        'r-btn--has-color': !!resolvedColor,
        'r-btn--icon': isIconBtn,
        'r-btn--block': block,
        'r-btn--loading': debouncedLoading,
        'r-btn--disabled': disabled,
        'r-btn--border': border,
        'r-btn--surface': surface,
      },
    ]"
    :style="{
      borderRadius: resolvedRounded,
      '--r-btn-color': resolvedColor,
    }"
    @pointerdown="onPointerDown"
    @keydown="onKeyDown"
  >
    <!-- Ripple wave container — overflow-hidden + border-radius:inherit
         keeps ripples inside the rounded silhouette without clipping
         the button's elevation shadow (which lives on .r-btn). -->
    <span ref="rippleContainer" class="r-btn__ripples" aria-hidden="true" />

    <!-- Loading spinner — overlays content while debouncedLoading is on.
         Lives in absolute positioning so the button's intrinsic width
         doesn't change between loading and idle states (no layout
         shift mid-action). -->
    <span v-if="debouncedLoading" class="r-btn__loader" aria-hidden="true">
      <RProgressCircular indeterminate :size="spinnerSize" :width="2" />
    </span>

    <span
      class="r-btn__content"
      :class="{ 'r-btn__content--hidden': debouncedLoading }"
    >
      <!-- Prepend zone — slot wins over prop. -->
      <span
        v-if="slots.prepend || (prependIcon && !isIconBtn)"
        class="r-btn__prepend"
      >
        <slot name="prepend">
          <RIcon v-if="prependIcon" :icon="prependIcon" />
        </slot>
      </span>

      <!-- Icon-only mode: when `icon` is a string, render the matching
           RIcon directly. When `icon` is bare `true`, fall through to
           the default slot so consumers can drop their own glyph in
           (e.g. RPlatformIcon on a GameCard badge) — without this
           branch the slot was silently dropped and the button rendered
           empty. -->
      <RIcon
        v-if="isIconBtn && iconString"
        :icon="iconString"
        class="r-btn__icon"
      />
      <span v-else-if="isIconBtn && slots.default" class="r-btn__icon-slot">
        <slot />
      </span>

      <!-- Default label slot — used when the button isn't icon-only.
           `.r-btn__label` carries `gap: inherit` so compound content
           (avatar + text + chevron in UserMenu, etc.) spaces correctly
           without each consumer having to override `:deep(.r-btn__label)`. -->
      <span v-if="!isIconBtn && slots.default" class="r-btn__label">
        <slot />
      </span>

      <!-- Append zone. -->
      <span
        v-if="slots.append || (appendIcon && !isIconBtn)"
        class="r-btn__append"
      >
        <slot name="append">
          <RIcon v-if="appendIcon" :icon="appendIcon" />
        </slot>
      </span>
    </span>
  </component>
</template>

<style scoped>
/* ── Base ──────────────────────────────────────────────────────── */
.r-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid transparent;
  font-family: inherit;
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0;
  text-transform: none;
  text-decoration: none;
  white-space: nowrap;
  user-select: none;
  cursor: pointer;
  /* Suppress native button defaults. */
  background: transparent;
  color: inherit;
  outline: none;
  /* Smooth tone / theme / state changes — RSwitch motion language. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Hover / active overlay — single `::before` painted in currentColor
   so it composes cleanly with any variant. No per-variant :hover
   rules; the overlay does the work. */
.r-btn::before {
  content: "";
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0;
  border-radius: inherit;
  pointer-events: none;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-btn:hover:not(.r-btn--disabled, :disabled)::before {
  opacity: 0.1;
}
.r-btn:active:not(.r-btn--disabled, :disabled)::before {
  opacity: 0.18;
}

/* ── Ripple — circular wave from the activation point ─────────── */
.r-btn__ripples {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border-radius: inherit;
  pointer-events: none;
  /* Sit between the hover overlay (::before) and the button content
     so the wave grazes the label without burying it. */
  z-index: 0;
}
.r-btn__ripples :deep(.r-btn__ripple) {
  position: absolute;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.28;
  transform: scale(0);
  pointer-events: none;
  animation: r-btn-ripple 550ms var(--r-motion-ease-out) forwards;
}
@keyframes r-btn-ripple {
  to {
    transform: scale(1);
    opacity: 0;
  }
}

/* ── Content / loader layout ──────────────────────────────────── */
.r-btn__content {
  display: inline-flex;
  align-items: center;
  gap: inherit;
  min-width: 0;
  /* Lift above the ripple wave so text/icons stay crisp during press. */
  position: relative;
  z-index: 1;
}
.r-btn__content--hidden {
  /* Keep layout, hide visually so spinner can overlay without shift. */
  visibility: hidden;
}
.r-btn__loader {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
  z-index: 2;
}

.r-btn__label {
  /* Flex so compound slot content (avatar + text + icon, etc.) aligns
     on the same vertical centerline instead of sitting on the text
     baseline like inline boxes would. `gap: inherit` pulls the gap
     from `.r-btn__content` (which itself inherits from `.r-btn`'s
     `gap: 8px`) so callers like UserMenu — avatar + name + chevron in
     one default slot — get correct spacing without a `:deep()`
     override at the consumer. */
  display: inline-flex;
  align-items: center;
  gap: inherit;
  min-width: 0;
}

/* Slot-driven icon-only content (e.g. `<RBtn icon><RPlatformIcon /></RBtn>`).
   Separate class from `.r-btn__icon` so the icon-font sizing rule
   (`.r-btn__icon { font-size: 1.25em }`) doesn't bleed into image-based
   slot content. Just a centered inline-flex shell. */
.r-btn__icon-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  line-height: 0;
}

.r-btn__prepend,
.r-btn__append,
.r-btn__icon {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  color: inherit;
}

/* ── Size ladder ───────────────────────────────────────────────── */
.r-btn--x-small {
  height: 20px;
  padding: 0 8px;
  font-size: 11px;
  gap: 4px;
}
.r-btn--small {
  height: 28px;
  padding: 0 12px;
  font-size: 13px;
  gap: 6px;
}
.r-btn--default {
  height: 36px;
  padding: 0 16px;
  font-size: 14px;
  gap: 8px;
}
.r-btn--large {
  height: 44px;
  padding: 0 20px;
  font-size: 15px;
  gap: 10px;
}
.r-btn--x-large {
  height: 52px;
  padding: 0 24px;
  font-size: 16px;
  gap: 12px;
}

/* Icon size scales with text — same 1.2em ratio RIcon uses. */
.r-btn .r-btn__prepend > .r-icon,
.r-btn .r-btn__append > .r-icon,
.r-btn .r-btn__icon {
  font-size: 1.25em;
}

/* ── Density — slight height compression ────────────────────────── */
.r-btn--density-comfortable {
  /* -4px from default — keeps the size ladder visually predictable. */
  height: calc(var(--r-btn-rest-h, auto) - 4px);
}
.r-btn--density-compact {
  height: calc(var(--r-btn-rest-h, auto) - 8px);
}
/* Map each size's rest height for the density calc. */
.r-btn--x-small {
  --r-btn-rest-h: 20px;
}
.r-btn--small {
  --r-btn-rest-h: 28px;
}
.r-btn--default {
  --r-btn-rest-h: 36px;
}
.r-btn--large {
  --r-btn-rest-h: 44px;
}
.r-btn--x-large {
  --r-btn-rest-h: 52px;
}
.r-btn--density-comfortable {
  height: calc(var(--r-btn-rest-h) - 4px);
}
.r-btn--density-compact {
  height: calc(var(--r-btn-rest-h) - 8px);
}

/* ── Icon-only — square hit area ──────────────────────────────── */
.r-btn--icon {
  padding: 0;
  width: var(--r-btn-rest-h);
}
.r-btn--icon.r-btn--density-comfortable {
  width: calc(var(--r-btn-rest-h) - 4px);
}
.r-btn--icon.r-btn--density-compact {
  width: calc(var(--r-btn-rest-h) - 8px);
}

/* ── Block — full width ────────────────────────────────────────── */
.r-btn--block {
  width: 100%;
  display: flex;
}

/* ── Variant: flat — solid fill ────────────────────────────────── */
.r-btn--flat.r-btn--has-color {
  background: var(--r-btn-color);
  color: white;
}
.r-btn--flat:not(.r-btn--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: elevated — solid + shadow ────────────────────────── */
.r-btn--elevated.r-btn--has-color {
  background: var(--r-btn-color);
  color: white;
  box-shadow: 0 2px 6px color-mix(in srgb, black 22%, transparent);
}
.r-btn--elevated:not(.r-btn--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
  box-shadow: 0 2px 6px color-mix(in srgb, black 18%, transparent);
}
.r-btn--elevated:hover:not(.r-btn--disabled, :disabled) {
  box-shadow: 0 4px 10px color-mix(in srgb, black 26%, transparent);
}

/* ── Variant: translucent — color-mix bg, coloured text ────────── */
.r-btn--translucent.r-btn--has-color {
  background: color-mix(in srgb, var(--r-btn-color) 16%, transparent);
  color: var(--r-btn-color);
}
.r-btn--translucent:not(.r-btn--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: outlined — border + text in tone ─────────────────── */
.r-btn--outlined {
  background: transparent;
}
.r-btn--outlined.r-btn--has-color {
  color: var(--r-btn-color);
  border-color: color-mix(in srgb, var(--r-btn-color) 50%, transparent);
}
.r-btn--outlined:not(.r-btn--has-color) {
  color: var(--r-color-fg);
  border-color: var(--r-color-border);
}

/* ── Variant: text — transparent, coloured text only ───────────── */
.r-btn--text {
  background: transparent;
}
.r-btn--text.r-btn--has-color {
  color: var(--r-btn-color);
}
.r-btn--text:not(.r-btn--has-color) {
  color: var(--r-color-fg);
}

/* ── Variant: plain — zero chrome, inherit ─────────────────────── */
.r-btn--plain {
  background: transparent;
  color: inherit;
}

/* ── `border` modifier — translucent currentColor border ───────── */
.r-btn--border {
  border-color: color-mix(in srgb, currentColor 40%, transparent);
}
.r-btn--border:hover:not(.r-btn--disabled, :disabled) {
  border-color: color-mix(in srgb, currentColor 65%, transparent);
}

/* ── `surface` modifier — tinted background composed onto any
   variant. Placed AFTER the variant rules so its single-class
   specificity wins on source order regardless of which variant the
   button uses (otherwise variants that set `background: transparent`
   would override). */
.r-btn--surface {
  background: var(--r-color-bg-elevated);
}

/* ── Disabled ──────────────────────────────────────────────────── */
.r-btn:disabled,
.r-btn--disabled {
  cursor: not-allowed;
  opacity: 0.45;
  pointer-events: none;
}

/* ── Reduced motion — drop hover overlay fade + ripple animation ── */
@media (prefers-reduced-motion: reduce) {
  .r-btn,
  .r-btn::before {
    transition: none;
  }
  .r-btn__ripples :deep(.r-btn__ripple) {
    animation: none;
    display: none;
  }
}
</style>
