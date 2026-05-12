<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { VBtn } from "vuetify/components/VBtn";

defineOptions({ inheritAttrs: false });

// RBtn — thin wrapper around v-btn with RomM v2 defaults:
//   - variant="flat" (our primary visual style)
//   - color undefined (neutral) — `primary` is reserved for primary
//     actions (Login, Add note, etc.). Pass `color="primary"`
//     explicitly when the button is THE primary action of its surface.
//   - rounded="md"
//   - font-weight medium, no uppercase (Vuetify's default)
//   - debounced spinner: when `loading` flips true, the spinner only
//     appears after `loadingDebounce` ms (default 200). Actions that
//     resolve quicker than that flash never paint a spinner. Going from
//     loading → not-loading is immediate.
//   - `border` modifier — adds a translucent border in the current
//     text colour. Pair with `variant="tonal"` + a `color` to get the
//     RTag pill recipe (translucent bg + coloured border + coloured
//     text) for chip-style activators (e.g. the Type cell in folder
//     mappings).
// Every Vuetify prop remains available via $attrs.
interface Props {
  variant?: "flat" | "text" | "elevated" | "tonal" | "outlined" | "plain";
  color?: string;
  rounded?: string | number | boolean;
  loading?: boolean;
  /** ms before the spinner appears after `loading` becomes true. */
  loadingDebounce?: number;
  disabled?: boolean;
  block?: boolean;
  size?: "x-small" | "small" | "default" | "large" | "x-large";
  density?: "default" | "comfortable" | "compact";
  icon?: string | boolean;
  ripple?: boolean;
  prependIcon?: string;
  appendIcon?: string;
  type?: "button" | "submit" | "reset";
  /** Adds a translucent border in the current text colour. Pairs
   *  cleanly with `variant="tonal"` to produce an RTag-style chip
   *  activator. */
  border?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "flat",
  color: undefined,
  rounded: "md",
  loading: false,
  loadingDebounce: 200,
  size: "default",
  density: "default",
  type: "button",
  prependIcon: undefined,
  appendIcon: undefined,
  icon: undefined,
  ripple: undefined,
  border: false,
});

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
</script>

<template>
  <VBtn
    v-bind="$attrs"
    class="r-btn"
    :class="{ 'r-btn--border': border }"
    :variant="variant"
    :color="color"
    :rounded="rounded"
    :loading="debouncedLoading"
    :disabled="disabled"
    :block="block"
    :size="size"
    :density="density"
    :icon="icon"
    :ripple="ripple"
    :prepend-icon="prependIcon"
    :append-icon="appendIcon"
    :type="type"
  >
    <template v-for="(_, slot) in $slots" #[slot]="slotProps">
      <slot :name="slot" v-bind="slotProps || {}" />
    </template>
  </VBtn>
</template>

<style scoped>
.r-btn {
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0;
  text-transform: none;
  /* Slightly muted at rest, fully illuminated on hover — same feel as
     GameActionBtn over cover art. Applied via opacity so it composes
     with any color (default/primary/error/...): the whole button —
     text, border, icon, background — brightens together on hover.
     Vuetify's own hover overlay still adds the bg lift on top. */
  opacity: 0.8;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-btn:hover:not(.v-btn--disabled) {
  opacity: 1;
}

/* Optical alignment for prepend/append icons.
   Three things stack to push the icon above the text's optical centre:
     1. Vuetify scales icons inside v-btn down to ~85% of text size
        (`.v-btn .v-icon { --v-icon-size-multiplier: 0.857 }`), so the
        icon sits in a smaller box centred on the line-box.
     2. The Material Design Icons font draws glyphs slightly above the
        em-square's geometric centre.
     3. We render labels in Title Case (text-transform: none, overriding
        Vuetify's default uppercase), so the visual mass of the label
        lives in the x-height band — below the line-box centre — while
        the icon stays at the geometric centre.
   A stock v-btn hides this because uppercase text shifts the optical
   centre back up to the cap-height. Nudging prepend/append slots 3px
   down lines the icon up with the x-height optical centre across our
   sizes. */
.r-btn :deep(.v-btn__prepend),
.r-btn :deep(.v-btn__append) {
  margin-block-start: 3px;
}

/* `border` modifier — adds a translucent border in the current text
   colour. `currentColor` picks up VBtn's text colour, which Vuetify
   has already painted from the `color` prop, so the border tints in
   lock-step. Paired with `variant="tonal"` it produces the RTag
   pill recipe (translucent bg + coloured border + coloured text)
   for chip-style activators. */
.r-btn--border {
  border: 1px solid color-mix(in srgb, currentColor 40%, transparent) !important;
}
.r-btn--border:hover:not(.v-btn--disabled) {
  border-color: color-mix(in srgb, currentColor 65%, transparent) !important;
}
</style>
