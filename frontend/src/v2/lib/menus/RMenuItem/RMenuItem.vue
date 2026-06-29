<script setup lang="ts">
// RMenuItem — clickable row used inside RMenuPanel.
//
// Renders either a `<button>` (default) or `<router-link>` when `to` is set,
// or an `<a>` when `href` is set. Stays visually consistent across all use
// cases: 15px leading-icon slot (left), label, 9px rounded hover bg.
//
// Variants:
//   * default — fg-secondary text, hover background var(--r-color-surface)
//   * active  — filled brand accent (radio-like "current" pick)
//   * danger  — red text, red-tinted hover (destructive actions)
//
// `textColor` / `iconColor` accept a token suffix (e.g. "brand-primary",
// "warning", "fav") and override the variant's defaults, so consumers can
// recolour the label and the leading icon independently. Passing either
// also forces the icon to full opacity (the implied semantic is "this row
// is visually emphasized").
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { opensInNewContext } from "@/v2/utils/mouseGestures";

defineOptions({ inheritAttrs: false });

type Variant = "default" | "active" | "danger";

interface Props {
  label?: string;
  icon?: string; // optional mdi class — falls back to the slot
  variant?: Variant;
  disabled?: boolean;
  // Routing — mutually exclusive; if neither is set we render a button.
  to?: string | object;
  href?: string;
  // `closeOnClick` makes the menu parent close when true (default). Handled
  // by the parent (RMenu auto-closes); this prop is mainly documentation
  // for consumers that wire their own open state.
  closeOnClick?: boolean;
  // Token-suffix overrides — `"brand-primary"` → `var(--r-color-brand-primary)`.
  textColor?: string;
  iconColor?: string;
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
  icon: undefined,
  variant: "default",
  to: undefined,
  href: undefined,
  closeOnClick: true,
  textColor: undefined,
  iconColor: undefined,
});

const emit = defineEmits<{
  (e: "click", event: MouseEvent): void;
}>();

// Use the imported RouterLink component (like RListItem), not the string
// `"router-link"`: see dynamicAttrs for why the attr surface has to be
// element-specific.
const elementType = computed(() => {
  if (props.to !== undefined && props.to !== null) return RouterLink;
  if (props.href !== undefined && props.href !== null) return "a";
  return "button";
});

// Per-element attrs. CRITICAL: never spread `href` onto RouterLink — a
// fallthrough `href` attribute (even `undefined`) clobbers the href
// RouterLink computes from `to`, leaving an <a> with NO href. Such an
// anchor isn't a real link: the browser offers no "open in new tab"
// context menu and Ctrl/⌘-click silently no-ops. Each branch therefore
// lists only the attributes that element actually takes.
const dynamicAttrs = computed<Record<string, unknown>>(() => {
  if (props.to !== undefined && props.to !== null) {
    return {
      to: props.to,
      role: "menuitem",
      "aria-disabled": props.disabled ? "true" : undefined,
    };
  }
  if (props.href !== undefined && props.href !== null) {
    return {
      href: props.disabled ? undefined : props.href,
      role: "menuitem",
      "aria-disabled": props.disabled ? "true" : undefined,
    };
  }
  return { type: "button", disabled: props.disabled };
});

// When the item is a link (`to`/`href`) opened with a new-tab / new-window
// gesture (Ctrl/⌘/Shift/Alt-click), let the browser handle it natively and
// suppress the `click` emit — otherwise a consumer's "close the menu"
// handler tears the <a> out of the DOM (RMenu teleports its panel) before
// the new tab opens, swallowing the gesture. RouterLink already declines
// to navigate in-app for these, so the default <a> action does the work.
function onClick(event: MouseEvent) {
  if (props.disabled) return;
  if ((props.to || props.href) && opensInNewContext(event)) return;
  emit("click", event);
}

const styleVars = computed(() => {
  const out: Record<string, string> = {};
  if (props.textColor) {
    out["--rmi-text"] = `var(--r-color-${props.textColor})`;
  }
  if (props.iconColor) {
    out["--rmi-icon"] = `var(--r-color-${props.iconColor})`;
  }
  if (props.textColor || props.iconColor) {
    out["--rmi-icon-opacity"] = "1";
  }
  return out;
});
</script>

<template>
  <component
    :is="elementType"
    v-bind="{ ...$attrs, ...dynamicAttrs }"
    class="r-menu-item r-touch-target"
    :class="{
      'r-menu-item--active': variant === 'active',
      'r-menu-item--danger': variant === 'danger',
      'r-menu-item--disabled': disabled,
    }"
    :style="styleVars"
    @click="onClick"
  >
    <span class="r-menu-item__icon">
      <slot name="icon">
        <!-- Render the MDI glyph if `icon` is set. -->
        <i v-if="icon" :class="['mdi', icon]" aria-hidden="true" />
      </slot>
    </span>
    <span class="r-menu-item__label">
      <slot>{{ label }}</slot>
    </span>
    <slot name="append" />
  </component>
</template>

<style scoped>
/* Variants and hover states route through CSS vars so an inline-style
   override (textColor / iconColor props) wins without specificity wars. */
.r-menu-item {
  appearance: none;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 12px;
  border-radius: 9px;
  cursor: pointer;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--rmi-text, var(--r-color-fg-secondary));
  font-family: inherit;
  text-align: left;
  text-decoration: none;
  width: 100%;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
  user-select: none;
}

.r-menu-item:hover:not(.r-menu-item--disabled) {
  --rmi-text: var(--r-color-fg);
  --rmi-icon-opacity: 1;
  background: var(--r-color-surface);
}

.r-menu-item__icon {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  display: grid;
  place-items: center;
  color: var(--rmi-icon, currentColor);
  opacity: var(--rmi-icon-opacity, 0.65);
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-menu-item__icon :deep(svg) {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.r-menu-item__icon :deep(.mdi) {
  font-size: 17px;
  line-height: 1;
}

.r-menu-item__label {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Active — single radio-like "current" pick. */
.r-menu-item--active,
.r-menu-item--active:hover:not(.r-menu-item--disabled) {
  --rmi-text: var(--r-color-brand-primary);
  --rmi-icon-opacity: 1;
}
.r-menu-item--active .r-menu-item__icon :deep(svg) {
  fill: currentColor;
  stroke: currentColor;
}

/* Danger — destructive actions. */
.r-menu-item--danger,
.r-menu-item--danger:hover:not(.r-menu-item--disabled) {
  --rmi-text: var(--r-color-danger);
}
.r-menu-item--danger {
  opacity: 0.85;
}
.r-menu-item--danger:hover:not(.r-menu-item--disabled) {
  background: color-mix(in srgb, var(--r-color-danger) 12%, transparent);
  opacity: 1;
}

/* Disabled — `pointer-events: none` also blocks native navigation on a
   disabled link item (anchors ignore the `disabled` attribute). */
.r-menu-item--disabled {
  opacity: 0.45;
  cursor: default;
  pointer-events: none;
}
</style>
