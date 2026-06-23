<script setup lang="ts">
// RBadge — wraps a default slot (the anchor element) and
// floats a small pill / dot / icon in one of eight positions (`top end`,
// `bottom start`, side anchors). Built for the unread-counter, status,
// favorite, online-indicator patterns.
//
// Pop-in spring animation reuses the RSwitch cubic-bezier so the
// vocabulary matches across the library. `pointer-events: none` on the
// pill so clicks pass through to the anchor.
//
// `content` accepts a string or number; numeric values past `max` get
// clamped with a `+` suffix ("99+"). `dot` renders a small bare circle
// (no content/icon). `bordered` adds a `--r-color-bg`-coloured ring so
// the badge reads cleanly on coloured anchors (avatars, etc).
//
// `inline` flips the badge from absolute-positioned floater to inline
// sibling — useful when you want a list badge that reads like "Inbox
// (4)" rather than an overlay.
import { computed } from "vue";
import RIcon from "../RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

type Anchor =
  | "top start"
  | "top end"
  | "bottom start"
  | "bottom end"
  | "top"
  | "bottom"
  | "start"
  | "end";

interface Props {
  content?: string | number;
  /** Tone keyword / legacy `romm-*` / any CSS colour. Default `"error"`
   *  for the red unread-count look. */
  color?: string;
  /** Bare dot — ignores `content` / `icon`. */
  dot?: boolean;
  /** Adds a 2px ring in the page bg colour so the badge contrasts on
   *  coloured anchors. */
  bordered?: boolean;
  /** Renders inline next to the slot content instead of floating over
   *  it. Useful for list-style "Item (3)" rows. */
  inline?: boolean;
  location?: Anchor;
  /** Show / hide the badge with a pop transition. */
  modelValue?: boolean;
  /** Pushes the badge further out of the anchor's corner — handy when
   *  the badge would otherwise sit too close to the content. */
  floating?: boolean;
  /** Numeric content > `max` is clamped: `max + "+"`. */
  max?: number;
  /** MDI icon shown inside the badge instead of text. */
  icon?: string;
}

const props = withDefaults(defineProps<Props>(), {
  content: undefined,
  color: "error",
  dot: false,
  bordered: false,
  inline: false,
  location: "top end",
  modelValue: true,
  floating: false,
  max: 99,
  icon: undefined,
});

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

const resolvedColor = computed<string>(() => {
  const c = props.color;
  if (!c) return TONE_MAP.error;
  return TONE_MAP[c] ?? c;
});

const displayContent = computed<string>(() => {
  const c = props.content;
  if (c === undefined || c === null || c === "") return "";
  const num = typeof c === "number" ? c : Number(c);
  if (!Number.isNaN(num) && Number.isFinite(num) && num > props.max) {
    return `${props.max}+`;
  }
  return String(c);
});

// Location → CSS class. `top end` becomes `r-badge--at-top-end`, etc.
const locationClass = computed(
  () => `r-badge--at-${props.location.replace(/\s+/g, "-")}`,
);
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-badge-wrap"
    :class="{ 'r-badge-wrap--inline': inline }"
  >
    <slot />
    <Transition name="r-badge-pop">
      <span
        v-if="modelValue"
        class="r-badge"
        :class="[
          locationClass,
          {
            'r-badge--dot': dot,
            'r-badge--bordered': bordered,
            'r-badge--floating': floating,
            'r-badge--inline': inline,
          },
        ]"
        :style="{ '--r-badge-color': resolvedColor }"
        aria-hidden="true"
      >
        <template v-if="!dot">
          <RIcon v-if="icon" :icon="icon" size="12" class="r-badge__icon" />
          <span v-else class="r-badge__content">{{ displayContent }}</span>
        </template>
      </span>
    </Transition>
  </span>
</template>

<style scoped>
/* ── Wrap (the anchor's positioning context) ───────────────────── */
.r-badge-wrap {
  display: inline-flex;
  position: relative;
  /* `align-items: center` keeps the slot content vertically centered
     when the wrapper is used inline next to text. */
  align-items: center;
}
.r-badge-wrap--inline {
  gap: 6px;
}

/* ── Badge pill ────────────────────────────────────────────────── */
.r-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--r-badge-color);
  color: white;
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  line-height: 1;
  border-radius: 999px;
  white-space: nowrap;
  padding: 2px 6px;
  min-width: 16px;
  height: 16px;
  pointer-events: none;
  /* Smooth tone / theme swaps + transform spring during the corner-pop
     animation below. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-badge__icon {
  color: inherit;
}

/* ── Dot variant ──────────────────────────────────────────────── */
.r-badge--dot {
  width: 10px;
  min-width: 10px;
  height: 10px;
  padding: 0;
}

/* ── Bordered — a soft page-bg ring so the badge pops on coloured
       anchors (avatars). ─────────────────────────────────────────── */
.r-badge--bordered {
  box-shadow: 0 0 0 2px var(--r-color-bg);
}

/* ── Inline — no absolute positioning, sits next to the anchor ─── */
.r-badge--inline {
  position: static;
  transform: none;
}

/* ── Floating positioning ─────────────────────────────────────── */
/* Each anchor sets its corner + a `translate` that centers the badge
   on the corner so the visible mass sits half inside / half outside
   the anchor. `scale` (from the enter/leave transition below) composes
   on top via the CSS `scale` property — keeps the translate untouched
   during the pop. */
.r-badge:not(.r-badge--inline) {
  position: absolute;
}

.r-badge--at-top-start {
  top: 0;
  left: 0;
  transform: translate(-50%, -50%);
}
.r-badge--at-top-end {
  top: 0;
  right: 0;
  transform: translate(50%, -50%);
}
.r-badge--at-bottom-start {
  bottom: 0;
  left: 0;
  transform: translate(-50%, 50%);
}
.r-badge--at-bottom-end {
  bottom: 0;
  right: 0;
  transform: translate(50%, 50%);
}

/* Side anchors — center along the edge. */
.r-badge--at-top {
  top: 0;
  left: 50%;
  transform: translate(-50%, -50%);
}
.r-badge--at-bottom {
  bottom: 0;
  left: 50%;
  transform: translate(-50%, 50%);
}
.r-badge--at-start {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
}
.r-badge--at-end {
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
}

/* Floating bumps the translate further out so the badge sits clearly
   outside the anchor — useful for icons inside dense toolbars where
   the default half-overlap would crowd the glyph. */
.r-badge--floating.r-badge--at-top-end {
  transform: translate(75%, -75%);
}
.r-badge--floating.r-badge--at-top-start {
  transform: translate(-75%, -75%);
}
.r-badge--floating.r-badge--at-bottom-end {
  transform: translate(75%, 75%);
}
.r-badge--floating.r-badge--at-bottom-start {
  transform: translate(-75%, 75%);
}

/* ── Pop animation — spring overshoot in / quick fade out ──────── */
.r-badge-pop-enter-active {
  transition:
    scale 320ms cubic-bezier(0.34, 1.56, 0.64, 1),
    opacity 200ms var(--r-motion-ease-out);
}
.r-badge-pop-leave-active {
  transition:
    scale 180ms var(--r-motion-ease-out),
    opacity 180ms var(--r-motion-ease-out);
}
/* `scale` is a separate property from `transform` (CSS Transforms L2),
   so animating it doesn't clobber the location-class `translate(...)` —
   the two compose: final transform = translate ∘ scale. */
.r-badge-pop-enter-from,
.r-badge-pop-leave-to {
  opacity: 0;
  scale: 0;
}
</style>
