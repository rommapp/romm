<script setup lang="ts">
// RListItem — semantic `<li>` wrapping a polymorphic
// interactive inner element:
//
//   • `to` → RouterLink (router-aware)
//   • `href` → <a>
//   • on-click listener present → <button>
//   • otherwise → <div> (non-interactive, display-only)
//
// The outer `<li>` keeps screen-reader counting correct regardless of
// the inner element. The inner element receives hover / active /
// disabled styling so a display-only RListItem doesn't react to mouse
// movement (no false affordance).
//
// `prepend-icon` + `prepend-avatar` are mutually exclusive — avatar
// wins if both are set (it's the more specific affordance). The
// `prepend` / `append` slots win over the props.
//
// Title + subtitle render in a stacked block; subtitle is muted. Pair
// with `density="compact"` on the parent RList for an inline single-
// line look (subtitle wraps under).
import { computed, useAttrs, useSlots } from "vue";
import { RouterLink, type RouteLocationRaw } from "vue-router";
import RAvatar from "../../primitives/RAvatar/RAvatar.vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  title?: string;
  subtitle?: string;
  value?: unknown;
  prependIcon?: string;
  appendIcon?: string;
  prependAvatar?: string;
  /** Highlights the item with the list's `--r-list-active-color`. */
  active?: boolean;
  disabled?: boolean;
  to?: RouteLocationRaw;
  href?: string;
  target?: string;
  rounded?: string | number | boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: undefined,
  subtitle: undefined,
  value: undefined,
  prependIcon: undefined,
  appendIcon: undefined,
  prependAvatar: undefined,
  active: false,
  disabled: false,
  to: undefined,
  href: undefined,
  target: undefined,
  rounded: undefined,
});

const slots = useSlots();
const attrs = useAttrs();

// Interactive if any of: `to` / `href` / `@click` (any onXxx listener).
// We can't observe individual handler types so we check for the click
// attr explicitly — anything else (focus, mouseenter…) doesn't promote
// the item to a button.
const hasClickHandler = computed(() => "onClick" in attrs);

const elementType = computed(() => {
  if (props.to !== undefined && props.to !== null) return RouterLink;
  if (props.href !== undefined && props.href !== null) return "a";
  if (hasClickHandler.value) return "button";
  return "div";
});

const dynamicAttrs = computed<Record<string, unknown>>(() => {
  if (props.to !== undefined && props.to !== null) {
    return {
      to: props.to,
      ariaDisabled: props.disabled ? "true" : undefined,
    };
  }
  if (props.href !== undefined && props.href !== null) {
    return {
      href: props.disabled ? undefined : props.href,
      target: props.target,
      ariaDisabled: props.disabled ? "true" : undefined,
    };
  }
  if (hasClickHandler.value) {
    return { type: "button", disabled: props.disabled };
  }
  return {};
});

const ROUNDED_MAP: Record<string, string> = {
  "0": "0",
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "999px",
};
const resolvedRounded = computed<string>(() => {
  const r = props.rounded;
  if (r === undefined || r === null || r === "") return "6px";
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

const isInteractive = computed(
  () => elementType.value !== "div" && !props.disabled,
);

// Avatar wins over icon when both are set — kept as a separate
// computed so the template stays readable.
const showAvatar = computed(() => !!props.prependAvatar);
const showPrependIcon = computed(
  () => !showAvatar.value && !!props.prependIcon,
);
</script>

<template>
  <li class="r-list-item-wrap">
    <component
      :is="elementType"
      v-bind="{ ...$attrs, ...dynamicAttrs }"
      class="r-list-item"
      :class="{
        'r-list-item--active': active,
        'r-list-item--disabled': disabled,
        'r-list-item--interactive': isInteractive,
        'r-touch-target': isInteractive,
      }"
      :style="{ borderRadius: resolvedRounded }"
    >
      <!-- Prepend zone — slot wins; otherwise avatar wins over icon. -->
      <span
        v-if="slots.prepend || showAvatar || showPrependIcon"
        class="r-list-item__prepend"
      >
        <slot name="prepend">
          <RAvatar v-if="showAvatar" :image="prependAvatar" size="32" />
          <RIcon
            v-else-if="showPrependIcon"
            :icon="prependIcon"
            class="r-list-item__icon"
          />
        </slot>
      </span>

      <!-- Body — title + subtitle stacked. The default slot lives on
           top so consumers can drop arbitrary content (forms, chips,
           etc.) instead of just text. -->
      <span class="r-list-item__body">
        <span v-if="title || slots.title" class="r-list-item__title">
          <slot name="title">{{ title }}</slot>
        </span>
        <span v-if="subtitle || slots.subtitle" class="r-list-item__subtitle">
          <slot name="subtitle">{{ subtitle }}</slot>
        </span>
        <slot />
      </span>

      <!-- Append zone — slot wins over `appendIcon` prop. -->
      <span v-if="slots.append || appendIcon" class="r-list-item__append">
        <slot name="append">
          <RIcon
            v-if="appendIcon"
            :icon="appendIcon"
            class="r-list-item__icon"
          />
        </slot>
      </span>
    </component>
  </li>
</template>

<style scoped>
/* The outer <li> is invisible — it's a semantic shell. All of the
   visual styling lives on the inner `.r-list-item`. */
.r-list-item-wrap {
  list-style: none;
  display: block;
}

.r-list-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: var(--r-list-item-h, 40px);
  padding: 6px 10px;
  width: 100%;
  background: transparent;
  color: inherit;
  text-align: left;
  text-decoration: none;
  font: inherit;
  border: 1px solid transparent;
  cursor: default;
  user-select: none;
  outline: none;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* button reset — when interactive, the inner element is a <button>;
   strip its native defaults so it reads as a list row, not a button. */
button.r-list-item,
a.r-list-item {
  appearance: none;
}

.r-list-item--interactive {
  cursor: pointer;
}

/* Hover overlay — single `::before` painted in currentColor.
   Composes cleanly with any list background. Only kicks in on
   interactive items so display-only rows don't react. */
.r-list-item::before {
  content: "";
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0;
  border-radius: inherit;
  pointer-events: none;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-list-item--interactive:hover::before {
  opacity: 0.08;
}
.r-list-item--interactive:active::before {
  opacity: 0.14;
}

/* ── Active state — tinted with the list's active colour ──────── */
.r-list-item--active {
  background: color-mix(
    in srgb,
    var(--r-list-active-color, var(--r-color-brand-primary)) 14%,
    transparent
  );
  color: var(--r-list-active-color, var(--r-color-brand-primary));
}
.r-list-item--active.r-list-item--interactive:hover::before {
  opacity: 0.06;
}

/* ── Disabled ──────────────────────────────────────────────────── */
.r-list-item--disabled {
  opacity: 0.45;
  pointer-events: none;
  cursor: not-allowed;
}

/* ── Layout regions ──────────────────────────────────────────── */
.r-list-item__prepend,
.r-list-item__append {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  color: inherit;
}
.r-list-item__icon {
  font-size: 18px;
  color: inherit;
}

.r-list-item__body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-list-item__title {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-list-item__subtitle {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-list-item--active .r-list-item__subtitle {
  /* Subtitle in an active row inherits the active tone but stays
     slightly faded so the title remains dominant. */
  color: color-mix(in srgb, currentColor 70%, transparent);
}
</style>
