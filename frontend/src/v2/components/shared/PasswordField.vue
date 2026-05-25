<script setup lang="ts">
// PasswordField — RTextField pre-wired with the password show/hide eye
// toggle (with tooltip) and a reveal animation. Uses the primitive's
// native append-inner adornment + tooltip; no slot workaround.
//
// Reveal animation: when the eye is toggled, the input text blurs and
// wobbles letter-spacing for a moment so the password ↔ text glyph
// swap is visually softened. The toggle icon flips on Y so its own
// eye/eye-off swap is hidden mid-rotation.
import { RTextField } from "@v2/lib";
import { computed, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    label?: string;
    autocomplete?: string;
    disabled?: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rules?: Array<(value: any) => true | string>;
    prependInnerIcon?: string;
    variant?: "outlined" | "filled" | "underlined" | "plain";
  }>(),
  {
    modelValue: "",
    label: undefined,
    autocomplete: "current-password",
    rules: undefined,
    prependInnerIcon: "mdi-lock",
    variant: "underlined",
  },
);

defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const { t } = useI18n();

const visible = ref(false);
const revealing = ref(false);
const toggleLabel = computed(() =>
  visible.value ? t("common.hide-password") : t("common.show-password"),
);

// Reveal animation timing. Total duration is `REVEAL_MS`; the `type`
// swap happens at `SWAP_AT_MS` (the blur peak) so the glyph change
// (• ↔ char) is masked by the blur. Kept aligned with the CSS
// `var(--r-motion-med)` duration (220ms) used in the keyframes.
const REVEAL_MS = 240;
const SWAP_AT_MS = 110;

let swapTimer: number | null = null;
let endTimer: number | null = null;

function clearTimers() {
  if (swapTimer != null) {
    window.clearTimeout(swapTimer);
    swapTimer = null;
  }
  if (endTimer != null) {
    window.clearTimeout(endTimer);
    endTimer = null;
  }
}

function onToggle() {
  if (props.disabled) return;
  clearTimers();
  // Restart cleanly: drop the class for one frame so the keyframes
  // re-run instead of being collapsed when clicks land back-to-back.
  revealing.value = false;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      revealing.value = true;
      swapTimer = window.setTimeout(() => {
        visible.value = !visible.value;
        swapTimer = null;
      }, SWAP_AT_MS);
      endTimer = window.setTimeout(() => {
        revealing.value = false;
        endTimer = null;
      }, REVEAL_MS);
    });
  });
}

onBeforeUnmount(clearTimers);
</script>

<template>
  <RTextField
    v-bind="$attrs"
    :model-value="modelValue"
    :label="label"
    :type="visible ? 'text' : 'password'"
    :variant="variant"
    :prepend-inner-icon="prependInnerIcon"
    :append-inner-icon="visible ? 'mdi-eye-off' : 'mdi-eye'"
    :append-inner-tooltip="toggleLabel"
    :autocomplete="autocomplete"
    :disabled="disabled"
    :rules="rules"
    class="r-password-field"
    :class="{ 'r-password-field--revealing': revealing }"
    @update:model-value="(v: string) => $emit('update:modelValue', v)"
    @click:append-inner="onToggle"
  >
    <!-- Forward every consumer-provided RTextField slot (prefix-label,
         prepend-inner, subtitle, details, …) without having to enumerate
         them. The append-inner slot is intentionally NOT forwarded — we
         own that adornment to render the eye toggle. -->
    <template v-for="(_, slot) of $slots" v-slot:[slot]="scope" :key="slot">
      <slot v-if="slot !== 'append-inner'" :name="slot" v-bind="scope" />
    </template>
  </RTextField>
</template>

<style scoped>
/* ── Reveal animation ─────────────────────────────────────────────
   The `.r-password-field--revealing` class is applied on RTextField's
   root for ~500ms after each toggle. We drive three things off it:
     1. The input text — strong blur + slight scale wobble. The
        underlying `type` swap (password ↔ text) lands at the blur
        peak so the glyph change is hidden behind the blur.
     2. The append-inner adornment icon (eye/eye-off) — Y-axis flip
        with a small scale pulse, hiding the icon swap mid-rotation.
     3. The prepend-inner adornment icon (lock by default) — short
        sway, so the field as a whole reads as "something happened".
   `:deep()` is required because the targeted nodes live inside
   RTextField's own scoped style tree. */
.r-password-field--revealing :deep(.r-text-field__input) {
  animation: r-pf-reveal-text var(--r-motion-med) var(--r-motion-ease-in-out);
  will-change: filter, letter-spacing, transform;
}

.r-password-field--revealing :deep(.r-text-field__adornment--append .r-icon) {
  animation: r-pf-reveal-eye var(--r-motion-med) var(--r-motion-ease-back);
}

.r-password-field--revealing :deep(.r-text-field__adornment--prepend .r-icon) {
  animation: r-pf-reveal-prepend var(--r-motion-med) var(--r-motion-ease-back);
}

@keyframes r-pf-reveal-text {
  0% {
    filter: blur(0);
    letter-spacing: 0;
    transform: scale(1);
  }
  40% {
    filter: blur(8px) brightness(1.2);
    letter-spacing: 0.18em;
    transform: scale(1.04);
  }
  60% {
    filter: blur(8px) brightness(1.2);
    letter-spacing: -0.06em;
    transform: scale(0.98);
  }
  100% {
    filter: blur(0);
    letter-spacing: 0;
    transform: scale(1);
  }
}

@keyframes r-pf-reveal-eye {
  0% {
    transform: rotateY(0) scale(1);
  }
  50% {
    transform: rotateY(90deg) scale(1.25);
  }
  100% {
    transform: rotateY(0) scale(1);
  }
}

@keyframes r-pf-reveal-prepend {
  0%,
  100% {
    transform: rotate(0);
  }
  35% {
    transform: rotate(-14deg);
  }
  70% {
    transform: rotate(10deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-password-field--revealing :deep(.r-text-field__input),
  .r-password-field--revealing :deep(.r-text-field__adornment--append .r-icon),
  .r-password-field--revealing
    :deep(.r-text-field__adornment--prepend .r-icon) {
    animation: none;
  }
}
</style>
