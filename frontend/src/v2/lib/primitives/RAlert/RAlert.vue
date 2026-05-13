<script setup lang="ts">
// RAlert — Vuetify-free. Banner with an auto-picked tone icon, title +
// body, optional close button, and a `<Transition>` mount that fades
// in / out so toggling visibility doesn't pop.
//
// `type` (`success | info | warning | error`) drives the colour and
// the default icon. `variant` controls the paint:
//   • translucent (default) — soft tinted fill, coloured text
//   • flat — solid colour fill, white text
//   • elevated — flat + drop shadow
//   • outlined — coloured border + transparent fill
//   • text — no chrome, just coloured text
//
// Slots:
//   • default — body (alternatively `text` prop)
//   • title — header (alternatively `title` prop)
//   • prepend — replaces the auto-picked icon
//   • append — extra content on the trailing edge
//
// v-model controls visibility. When `closable` is set, clicking the
// X emits `click:close` and flips `modelValue` to false; the leave
// transition runs before the DOM is removed.
import { computed, useSlots } from "vue";
import RIcon from "../RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Tone keyword — drives colour + default icon. */
  type?: "success" | "info" | "warning" | "error";
  variant?: "flat" | "elevated" | "translucent" | "outlined" | "text";
  closable?: boolean;
  /** MDI icon override, or `false` to suppress the auto-icon. */
  icon?: string | false;
  density?: "default" | "comfortable" | "compact";
  title?: string;
  /** Shortcut for the default slot. */
  text?: string;
  rounded?: string | number | boolean;
  /** v-model visibility. */
  modelValue?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  type: undefined,
  variant: "translucent",
  closable: false,
  icon: undefined,
  density: "default",
  title: undefined,
  text: undefined,
  rounded: "md",
  modelValue: true,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "click:close", evt: MouseEvent): void;
}>();

const slots = useSlots();

// Auto icon per type — the alert reads the alert tone at a glance.
const TYPE_ICON: Record<string, string> = {
  success: "mdi-check-circle",
  info: "mdi-information",
  warning: "mdi-alert",
  error: "mdi-alert-octagon",
};

const TYPE_COLOR: Record<string, string> = {
  success: "var(--r-color-success)",
  info: "var(--r-color-info)",
  warning: "var(--r-color-warning)",
  error: "var(--r-color-danger)",
};

const resolvedColor = computed<string | undefined>(() =>
  props.type ? TYPE_COLOR[props.type] : undefined,
);

const resolvedIcon = computed<string | undefined>(() => {
  // Explicit `false` suppresses the icon. Explicit string overrides.
  if (props.icon === false) return undefined;
  if (typeof props.icon === "string") return props.icon;
  if (props.type) return TYPE_ICON[props.type];
  return undefined;
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
  if (r === undefined || r === null || r === "") return "8px";
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

// Role hint per type — error stays `alert` (assertive), the rest read
// as `status` (polite). Matches WAI-ARIA semantics so screen readers
// don't interrupt for a success banner.
const ariaRole = computed(() => (props.type === "error" ? "alert" : "status"));

function close(evt: MouseEvent) {
  emit("click:close", evt);
  emit("update:modelValue", false);
}
</script>

<template>
  <Transition name="r-alert">
    <div
      v-if="modelValue"
      v-bind="$attrs"
      class="r-alert"
      :class="[
        `r-alert--${variant}`,
        `r-alert--density-${density}`,
        {
          'r-alert--has-color': !!resolvedColor,
          'r-alert--has-title': !!(title || slots.title),
        },
      ]"
      :style="{
        borderRadius: resolvedRounded,
        '--r-alert-color': resolvedColor,
      }"
      :role="ariaRole"
    >
      <!-- Prepend zone — slot wins over auto-icon. -->
      <span v-if="slots.prepend || resolvedIcon" class="r-alert__prepend">
        <slot name="prepend">
          <RIcon
            v-if="resolvedIcon"
            :icon="resolvedIcon"
            class="r-alert__icon"
          />
        </slot>
      </span>

      <!-- Body — title + body text. Each is optional. -->
      <div class="r-alert__body">
        <div v-if="title || slots.title" class="r-alert__title">
          <slot name="title">{{ title }}</slot>
        </div>
        <div v-if="text || slots.default" class="r-alert__content">
          <slot>{{ text }}</slot>
        </div>
      </div>

      <!-- Append zone — caller-provided actions / links. -->
      <span v-if="slots.append" class="r-alert__append">
        <slot name="append" />
      </span>

      <!-- Close button — only rendered when `closable`. -->
      <button
        v-if="closable"
        type="button"
        class="r-alert__close"
        :aria-label="'Close'"
        @click="close"
      >
        <RIcon icon="mdi-close" class="r-alert__close-icon" />
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.r-alert {
  display: flex;
  /* Default: single-line alert — icon vertical centre = text vertical
     centre, which reads as "aligned". When a title pushes the body
     to 2+ lines, `r-alert--has-title` overrides to `flex-start` so
     the icon hugs the top of the title rather than floating between
     title and body. */
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid transparent;
  font-size: var(--r-font-size-sm);
  line-height: 1.45;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-alert--has-title {
  align-items: flex-start;
}

/* ── Density compression ──────────────────────────────────────── */
.r-alert--density-comfortable {
  padding: 10px 14px;
  gap: 10px;
}
.r-alert--density-compact {
  padding: 8px 12px;
  gap: 8px;
  font-size: var(--r-font-size-xs);
}

/* ── Layout regions ──────────────────────────────────────────── */
.r-alert__prepend,
.r-alert__append {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}
/* In the multi-line / title case the alert is top-aligned — nudge
   the icon down 1px so its optical centre matches the title's first
   line baseline (otherwise mixed-case glyphs sit slightly low). */
.r-alert--has-title .r-alert__prepend {
  margin-top: 1px;
}
.r-alert__icon {
  font-size: 1.25em;
  color: var(--r-alert-color, currentColor);
}

.r-alert__body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-alert__title {
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-alert-color, currentColor);
}
.r-alert__content {
  color: inherit;
  /* Slight tone-down on body text vs title so the hierarchy reads. */
  opacity: 0.92;
}

/* ── Close button — own hover halo so it reads as separate ────── */
.r-alert__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  margin-right: -4px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  border-radius: 50%;
  opacity: 0.7;
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-alert__close:hover {
  opacity: 1;
  background: color-mix(in srgb, currentColor 12%, transparent);
}
.r-alert__close:active {
  transform: scale(0.9);
}
/* In the title (top-aligned) case the close button needs a nudge so
   it lines up with the title row instead of floating below it. */
.r-alert--has-title .r-alert__close {
  margin-top: -2px;
}
.r-alert__close-icon {
  font-size: 14px;
}

/* ── Variant: translucent (default) — soft tinted fill ────────── */
.r-alert--translucent.r-alert--has-color {
  background: color-mix(in srgb, var(--r-alert-color) 14%, transparent);
  color: var(--r-alert-color);
  border-color: color-mix(in srgb, var(--r-alert-color) 28%, transparent);
}
.r-alert--translucent:not(.r-alert--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
  border-color: var(--r-color-border);
}

/* ── Variant: flat — solid colour fill ───────────────────────── */
.r-alert--flat.r-alert--has-color {
  background: var(--r-alert-color);
  color: white;
}
.r-alert--flat.r-alert--has-color .r-alert__icon,
.r-alert--flat.r-alert--has-color .r-alert__title {
  color: white;
}
.r-alert--flat:not(.r-alert--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: elevated — flat + shadow ───────────────────────── */
.r-alert--elevated.r-alert--has-color {
  background: var(--r-alert-color);
  color: white;
  box-shadow: 0 4px 12px
    color-mix(in srgb, var(--r-alert-color) 35%, transparent);
}
.r-alert--elevated.r-alert--has-color .r-alert__icon,
.r-alert--elevated.r-alert--has-color .r-alert__title {
  color: white;
}
.r-alert--elevated:not(.r-alert--has-color) {
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg);
  box-shadow: 0 4px 12px color-mix(in srgb, black 22%, transparent);
}

/* ── Variant: outlined — border + transparent fill ───────────── */
.r-alert--outlined {
  background: transparent;
}
.r-alert--outlined.r-alert--has-color {
  color: var(--r-alert-color);
  border-color: color-mix(in srgb, var(--r-alert-color) 50%, transparent);
}
.r-alert--outlined:not(.r-alert--has-color) {
  color: var(--r-color-fg);
  border-color: var(--r-color-border);
}

/* ── Variant: text — no chrome, coloured text only ───────────── */
.r-alert--text {
  background: transparent;
  border-color: transparent;
}
.r-alert--text.r-alert--has-color {
  color: var(--r-alert-color);
}
.r-alert--text:not(.r-alert--has-color) {
  color: var(--r-color-fg);
}

/* ── Mount / unmount transition ──────────────────────────────── */
/* Slides + fades when toggled — keeps closing alerts from popping out
   of the document. The 8px slide is subtle enough to read as motion
   without being a "drawer". */
.r-alert-enter-active {
  transition:
    opacity 200ms var(--r-motion-ease-out),
    transform 200ms var(--r-motion-ease-out);
}
.r-alert-leave-active {
  transition:
    opacity 160ms var(--r-motion-ease-out),
    transform 160ms var(--r-motion-ease-out);
}
.r-alert-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.r-alert-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .r-alert-enter-active,
  .r-alert-leave-active {
    transition: opacity 100ms linear;
  }
  .r-alert-enter-from,
  .r-alert-leave-to {
    transform: none;
  }
}
</style>
