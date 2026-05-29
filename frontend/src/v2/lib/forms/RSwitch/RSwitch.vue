<script setup lang="ts">
// RSwitch — iOS-style on/off control. A 36×20 track with a 14px knob
// that slides on toggle, brand-primary background when on. A native
// `<button role="switch">` — focusable, keyboard- and gamepad-friendly,
// with a visible footprint of exactly 36×20.
//
// Optional `label` renders to the right of the switch (clicking the
// label toggles too). Without a label, only the switch paints — useful
// inside table cells / dense rows. `SettingsToggleRow` is a separate
// composite that wraps RSwitch with a full-row label + description
// click target.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue: boolean;
  /** Optional inline label rendered next to the switch. */
  label?: string;
  /** Visual size — `default` is the 36×20 track, `small` shrinks to
   *  28×16. Both keep the same hit-area on touch / pad. */
  size?: "default" | "small";
  disabled?: boolean;
  /** Accessible label for the switch when there's no visible label. */
  ariaLabel?: string;
  /** Render as a passive `<span>` (no button semantics, no click
   *  handler, no role). Useful when an outer wrapper already owns the
   *  interactive surface — e.g. `SettingsToggleRow` is a button whose
   *  whole area toggles, and the visual switch on the right is just a
   *  state indicator. Nested `<button>`s would be invalid HTML. */
  static?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
  size: "default",
  disabled: false,
  ariaLabel: undefined,
  static: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const effectiveAriaLabel = computed(
  () => props.ariaLabel ?? props.label ?? "Toggle",
);

function toggle() {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
}
</script>

<template>
  <component
    :is="static ? 'span' : 'button'"
    v-bind="$attrs"
    :type="static ? undefined : 'button'"
    :role="static ? undefined : 'switch'"
    :aria-checked="static ? undefined : modelValue"
    :aria-label="static ? undefined : effectiveAriaLabel"
    :aria-hidden="static ? 'true' : undefined"
    :disabled="static ? undefined : disabled || undefined"
    class="r-switch"
    :class="[
      `r-switch--${size}`,
      {
        'r-switch--on': modelValue,
        'r-switch--disabled': disabled,
        'r-switch--static': static,
      },
    ]"
    @click="static ? undefined : toggle()"
  >
    <span class="r-switch__track" aria-hidden="true">
      <span class="r-switch__knob" />
    </span>
    <span v-if="label" class="r-switch__label">{{ label }}</span>
  </component>
</template>

<style scoped>
/* Motion design:
   • Knob slides with a slight overshoot (spring-like cubic-bezier) so
     the toggle feels physical, not robotic.
   • Active press squashes the knob horizontally in the direction of
     motion — a tiny haptic cue that the gesture registered before the
     state actually flips.
   • Hover lifts the knob via a subtle ring shadow.
   • The track gains a soft inner highlight + outer glow when on so the
     state change reads from across the page, not just at the switch.
   • Translate (GPU-friendly) instead of `left` for the knob so the
     spring is smooth on dense pages (e.g. inside a long table).
   `--r-switch-travel` per size keeps the distance configurable in one
   spot — change it once if you change the track/knob geometry. */

.r-switch {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  color: inherit;
  font: inherit;
  /* The press squash is keyed off the *active* state of the button.
     Vertical alignment of the track stays put because the squash only
     modifies the knob, never the track. */
}
.r-switch--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

/* Static mode — the switch is just a visual state indicator inside a
   bigger interactive surface. Drop pointer affordances; the outer
   element supplies them. */
.r-switch--static {
  cursor: inherit;
  pointer-events: none;
}

/* ── Track ──────────────────────────────────────────────────────── */
.r-switch__track {
  position: relative;
  flex-shrink: 0;
  border-radius: 999px;
  background: var(--r-color-border-strong);
  overflow: hidden;
  transition:
    background 260ms cubic-bezier(0.45, 0.05, 0.55, 0.95),
    box-shadow 260ms cubic-bezier(0.45, 0.05, 0.55, 0.95);
}

/* Subtle inner sheen — a downward-fading highlight that gives the
   track a touch of dimensionality without committing to skeuomorphism. */
.r-switch__track::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, white 8%, transparent),
    transparent 70%
  );
  pointer-events: none;
}

/* ── Knob ───────────────────────────────────────────────────────── */
.r-switch__knob {
  position: absolute;
  top: 3px;
  left: 3px;
  border-radius: 50%;
  background: var(--r-color-fg);
  transform: translateX(0) scaleX(1);
  /* Origin sits on the outer edge of the knob in each state (left when
     off, right when on — see `.r-switch--on .r-switch__knob`) so the
     press squash always grows toward the centre of the track. With a
     centred origin the off-state squash visibly bulges out the left
     side; anchoring to the outer edge keeps growth one-sided. */
  transform-origin: left center;
  /* Spring easing — slight overshoot then settle. The base duration is
     a touch longer than the v2 default so the spring has room to
     breathe. */
  transition:
    transform 340ms cubic-bezier(0.34, 1.56, 0.64, 1),
    background 200ms var(--r-motion-ease-out),
    box-shadow 200ms var(--r-motion-ease-out),
    width 200ms var(--r-motion-ease-out);
  box-shadow:
    0 1px 2px color-mix(in srgb, black 22%, transparent),
    0 0 0 0 transparent;
}

/* ── Size ladder ───────────────────────────────────────────────── */
.r-switch--default .r-switch__track {
  width: 36px;
  height: 20px;
  --r-switch-travel: 16px;
}
.r-switch--default .r-switch__knob {
  width: 14px;
  height: 14px;
}

.r-switch--small .r-switch__track {
  width: 28px;
  height: 16px;
  --r-switch-travel: 12px;
}
.r-switch--small .r-switch__knob {
  width: 10px;
  height: 10px;
}

/* ── On state ───────────────────────────────────────────────────── */
.r-switch--on .r-switch__knob {
  background: var(--r-color-overlay-emphasis-fg);
  transform: translateX(var(--r-switch-travel)) scaleX(1);
  transform-origin: right center;
}
.r-switch--on .r-switch__track {
  background: var(--r-color-brand-primary);
  /* Soft outer glow + an inner top highlight that hugs the brand
     colour, so the state change is legible at distance. */
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 18%, transparent),
    0 0 12px color-mix(in srgb, var(--r-color-brand-primary) 38%, transparent);
}

/* ── Hover — knob picks up a halo, track lightens a hair ──────── */
.r-switch:hover:not(.r-switch--disabled) .r-switch__knob {
  box-shadow:
    0 2px 4px color-mix(in srgb, black 28%, transparent),
    0 0 0 5px color-mix(in srgb, var(--r-color-fg) 10%, transparent);
}
.r-switch--on:hover:not(.r-switch--disabled) .r-switch__knob {
  box-shadow:
    0 2px 4px color-mix(in srgb, black 28%, transparent),
    0 0 0 5px color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
}

/* ── Active press — squash in the direction of motion ───────────
   The shorter, eased transition lets the squash feel snappy on touch
   down. When the click resolves, the longer spring transition above
   takes over and the knob settles into its new position. */
.r-switch:active:not(.r-switch--disabled) .r-switch__knob {
  transform: translateX(0) scaleX(1.35);
  transition: transform 110ms var(--r-motion-ease-out);
}
.r-switch--on:active:not(.r-switch--disabled) .r-switch__knob {
  transform: translateX(var(--r-switch-travel)) scaleX(1.35);
}

/* Static mode — the switch is a passive `<span>` with `pointer-events:
   none`, so `:active` lives on the interactive ancestor (e.g.
   `SettingsToggleRow`'s outer `<button>`), never on `.r-switch` itself.
   Mirror the squash from the closest active button so the haptic cue
   still reads when the row is the click target. */
button:active:not(:disabled)
  .r-switch--static:not(.r-switch--disabled)
  .r-switch__knob {
  transform: translateX(0) scaleX(1.35);
  transition: transform 110ms var(--r-motion-ease-out);
}
button:active:not(:disabled)
  .r-switch--static.r-switch--on:not(.r-switch--disabled)
  .r-switch__knob {
  transform: translateX(var(--r-switch-travel)) scaleX(1.35);
}

/* ── Label ──────────────────────────────────────────────────────── */
.r-switch__label {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  transition: color 200ms var(--r-motion-ease-out);
}
.r-switch--on .r-switch__label {
  color: var(--r-color-brand-primary);
}

/* Focus ring is modality-gated by global.css — we don't paint a ring
   here, but we do hide the default outline so it doesn't double up. */
.r-switch:focus {
  outline: none;
}

/* Respect reduced-motion preferences — drop the spring + squash and
   fall back to a plain colour swap so motion-sensitive users aren't
   served the bouncy variant. */
@media (prefers-reduced-motion: reduce) {
  .r-switch__knob,
  .r-switch__track,
  .r-switch__label {
    transition: none;
  }
  .r-switch:active:not(.r-switch--disabled) .r-switch__knob,
  button:active:not(:disabled)
    .r-switch--static:not(.r-switch--disabled)
    .r-switch__knob {
    transform: translateX(0) scaleX(1);
  }
  .r-switch--on:active:not(.r-switch--disabled) .r-switch__knob,
  button:active:not(:disabled)
    .r-switch--static.r-switch--on:not(.r-switch--disabled)
    .r-switch__knob {
    transform: translateX(var(--r-switch-travel)) scaleX(1);
  }
}
</style>
