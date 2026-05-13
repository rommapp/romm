<script setup lang="ts">
// RCarousel — slide-through viewer for an array of items.
//
// Two modes:
//   * inline      — renders the active item in-place with prev/next chrome.
//   * fullscreen  — teleports a viewport-filling overlay with scrim, close
//                   button, and centred item. Drives its own enter/leave
//                   animation; mount/unmount with v-if to play it.
//
// The default slot owns item rendering, so the same primitive serves
// images, video frames, charts — anything indexed by an array.
//
// Navigation
//   * Arrow keys (←/→ on key/pad — gamepad arrows are rewritten to
//     keyboard events by `useGamepad`).
//   * Home / End jump to first / last.
//   * Escape closes when fullscreen.
//   * Click on backdrop closes when fullscreen.
//
// Transitions
//   * Active item swap uses a directional slide+fade (`r-carousel-next`
//     vs `r-carousel-prev`), so going forward and going back read
//     differently — no ambiguous crossfade.
//   * On fullscreen mount the panel scale-pops with spring easing.
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

// Items are typed as `unknown` so the primitive stays free of any
// product-domain knowledge (premise II.criterion-2). Consumers narrow the
// slot payload with `v-slot="{ item }"` and an explicit cast or local
// generic component.
type CarouselItem = unknown;

interface Props {
  /** Active item index. */
  modelValue: number;
  /** Items array — the slot decides how each one is rendered. */
  items: readonly CarouselItem[];
  /** Render as a viewport-filling overlay with scrim and close button. */
  fullscreen?: boolean;
  /** Wrap from last → first and first → last. */
  loop?: boolean;
  /** Show "n / total" counter. Defaults to true when `items.length > 1`. */
  showCounter?: boolean;
  /** Show prev/next arrows. Defaults to true when `items.length > 1`. */
  showArrows?: boolean;
  /** Show a thumbnail strip below the active item. */
  showThumbnails?: boolean;
  /** Localised label for the close button. */
  closeLabel?: string;
  /** Localised label for the prev button. */
  prevLabel?: string;
  /** Localised label for the next button. */
  nextLabel?: string;
  /** Accessibility label for the carousel region. */
  ariaLabel?: string;
}

const props = withDefaults(defineProps<Props>(), {
  fullscreen: false,
  loop: true,
  showCounter: undefined,
  showArrows: undefined,
  showThumbnails: false,
  closeLabel: "Close",
  prevLabel: "Previous",
  nextLabel: "Next",
  ariaLabel: undefined,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: number): void;
  (e: "prev"): void;
  (e: "next"): void;
  (e: "close"): void;
}>();

defineSlots<{
  default(slotProps: {
    item: CarouselItem;
    index: number;
    active: boolean;
  }): unknown;
  thumbnail(slotProps: {
    item: CarouselItem;
    index: number;
    active: boolean;
  }): unknown;
  empty(): unknown;
  counter(slotProps: { index: number; total: number }): unknown;
}>();

// ---- Derived ---------------------------------------------------------------

const total = computed(() => props.items.length);
const hasMany = computed(() => total.value > 1);

const showArrowsResolved = computed(() =>
  props.showArrows !== undefined ? props.showArrows : hasMany.value,
);
const showCounterResolved = computed(() =>
  props.showCounter !== undefined ? props.showCounter : hasMany.value,
);

const safeIndex = computed(() => {
  if (total.value === 0) return 0;
  const i = Math.max(0, Math.min(props.modelValue, total.value - 1));
  return i;
});
const activeItem = computed<CarouselItem | undefined>(
  () => props.items[safeIndex.value],
);

// `direction` drives the slide direction of the <Transition> below. Updated
// before we emit a new index so the transition class on the way out matches
// the arrow that was pressed.
type Direction = "next" | "prev";
const direction = ref<Direction>("next");
const transitionName = computed(() =>
  direction.value === "next" ? "r-carousel-next" : "r-carousel-prev",
);

// ---- Navigation ------------------------------------------------------------

function go(step: 1 | -1) {
  if (total.value === 0) return;
  direction.value = step === 1 ? "next" : "prev";
  let next = safeIndex.value + step;
  if (next < 0) {
    if (!props.loop) return;
    next = total.value - 1;
  } else if (next >= total.value) {
    if (!props.loop) return;
    next = 0;
  }
  if (next === safeIndex.value) return;
  if (step === 1) emit("next");
  else emit("prev");
  emit("update:modelValue", next);
}

function jumpTo(index: number) {
  if (index < 0 || index >= total.value || index === safeIndex.value) return;
  direction.value = index > safeIndex.value ? "next" : "prev";
  emit("update:modelValue", index);
}

function close() {
  emit("close");
}

// ---- Keyboard --------------------------------------------------------------

function onKeydown(event: KeyboardEvent) {
  // Don't hijack typing in inputs that may live inside slots.
  const target = event.target as HTMLElement | null;
  const tag = target?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

  switch (event.key) {
    case "ArrowRight":
      event.preventDefault();
      go(1);
      break;
    case "ArrowLeft":
      event.preventDefault();
      go(-1);
      break;
    case "Home":
      if (total.value > 0) {
        event.preventDefault();
        jumpTo(0);
      }
      break;
    case "End":
      if (total.value > 0) {
        event.preventDefault();
        jumpTo(total.value - 1);
      }
      break;
    case "Escape":
      if (props.fullscreen) {
        event.preventDefault();
        close();
      }
      break;
  }
}

onMounted(() => {
  if (props.fullscreen) window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  if (props.fullscreen) window.removeEventListener("keydown", onKeydown);
});

// ---- Thumbnail scroll-into-view -------------------------------------------

const thumbStripRef = ref<HTMLElement | null>(null);

watch(safeIndex, async () => {
  if (!props.showThumbnails) return;
  await nextTick();
  const strip = thumbStripRef.value;
  if (!strip) return;
  const child = strip.children[safeIndex.value] as HTMLElement | undefined;
  child?.scrollIntoView({
    block: "nearest",
    inline: "center",
    behavior: "smooth",
  });
});

// ---- Backdrop click --------------------------------------------------------

function onBackdropClick(event: MouseEvent) {
  if (!props.fullscreen) return;
  if (event.target === event.currentTarget) close();
}
</script>

<template>
  <!-- Fullscreen mode: teleport an overlay to <body> so it escapes any
       transformed ancestor. Scoped class lookup still works because the
       teleported root keeps its data-v attribute.
       — Backdrop click dismisses; keyboard equivalent is the window-level
         Escape listener wired in onMounted. The `role="dialog"` makes the
         element semantically interactive but the lint rule only recognises
         button/link-shaped roles, hence the disables. -->
  <Teleport v-if="fullscreen" to="body">
    <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events,vuejs-accessibility/no-static-element-interactions -->
    <div
      v-bind="$attrs"
      class="r-carousel r-carousel--fullscreen r-v2"
      role="dialog"
      aria-modal="true"
      :aria-label="ariaLabel"
      tabindex="-1"
      @click="onBackdropClick"
    >
      <button
        type="button"
        class="r-carousel__close"
        :aria-label="closeLabel"
        @click="close"
      >
        <RIcon icon="mdi-close" size="20" />
      </button>

      <!-- Stage: holds the transitioning active item, vertically + horizontally
           centred. The .self click dismisses on the padded backdrop area
           around the image — outside-click on the outer wrapper would miss
           those gaps because they're nested inside the stage. -->
      <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events,vuejs-accessibility/no-static-element-interactions -->
      <div class="r-carousel__stage" @click.self="onBackdropClick">
        <Transition :name="transitionName" mode="out-in">
          <div
            :key="safeIndex"
            class="r-carousel__item r-carousel__item--fullscreen"
          >
            <slot
              v-if="activeItem !== undefined"
              :item="activeItem"
              :index="safeIndex"
              :active="true"
            />
            <slot v-else name="empty" />
          </div>
        </Transition>
      </div>

      <button
        v-if="showArrowsResolved"
        type="button"
        class="r-carousel__nav r-carousel__nav--prev"
        :aria-label="prevLabel"
        :disabled="!loop && safeIndex === 0"
        @click.stop="go(-1)"
      >
        <RIcon icon="mdi-chevron-left" size="36" />
      </button>
      <button
        v-if="showArrowsResolved"
        type="button"
        class="r-carousel__nav r-carousel__nav--next"
        :aria-label="nextLabel"
        :disabled="!loop && safeIndex === total - 1"
        @click.stop="go(1)"
      >
        <RIcon icon="mdi-chevron-right" size="36" />
      </button>

      <!-- Footer column: thumbnails first, counter below them so the chip
           never floats over the previews. -->
      <div v-if="showThumbnails && hasMany" class="r-carousel__thumbs-wrap">
        <div ref="thumbStripRef" class="r-carousel__thumbs">
          <button
            v-for="(item, i) in items"
            :key="i"
            type="button"
            class="r-carousel__thumb"
            :class="{ 'r-carousel__thumb--active': i === safeIndex }"
            :aria-label="`${i + 1} / ${total}`"
            :aria-current="i === safeIndex ? 'true' : undefined"
            @click.stop="jumpTo(i)"
          >
            <slot
              name="thumbnail"
              :item="item"
              :index="i"
              :active="i === safeIndex"
            />
          </button>
        </div>
      </div>

      <div
        v-if="showCounterResolved"
        class="r-carousel__counter r-carousel__counter--footer"
      >
        <slot name="counter" :index="safeIndex" :total="total">
          {{ safeIndex + 1 }} / {{ total }}
        </slot>
      </div>
    </div>
  </Teleport>

  <!-- Inline mode: renders in place. Same transition logic, no scrim.
       Keydown is best-effort — gamepad arrows reach this only if focus
       lands inside the carousel; for global key/pad handling, prefer
       fullscreen mode where the listener is on `window`. -->
  <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -->
  <div
    v-else
    v-bind="$attrs"
    class="r-carousel r-carousel--inline r-v2"
    :aria-label="ariaLabel"
    role="region"
    @keydown="onKeydown"
  >
    <div class="r-carousel__stage">
      <Transition :name="transitionName" mode="out-in">
        <div :key="safeIndex" class="r-carousel__item">
          <slot
            v-if="activeItem !== undefined"
            :item="activeItem"
            :index="safeIndex"
            :active="true"
          />
          <slot v-else name="empty" />
        </div>
      </Transition>

      <RBtn
        v-if="showArrowsResolved"
        icon="mdi-chevron-left"
        variant="translucent"
        size="small"
        class="r-carousel__nav r-carousel__nav--prev"
        :aria-label="prevLabel"
        :disabled="!loop && safeIndex === 0"
        @click.stop="go(-1)"
      />
      <RBtn
        v-if="showArrowsResolved"
        icon="mdi-chevron-right"
        variant="translucent"
        size="small"
        class="r-carousel__nav r-carousel__nav--next"
        :aria-label="nextLabel"
        :disabled="!loop && safeIndex === total - 1"
        @click.stop="go(1)"
      />

      <div v-if="showCounterResolved" class="r-carousel__counter">
        <slot name="counter" :index="safeIndex" :total="total">
          {{ safeIndex + 1 }} / {{ total }}
        </slot>
      </div>
    </div>

    <div v-if="showThumbnails && hasMany" class="r-carousel__thumbs-wrap">
      <div ref="thumbStripRef" class="r-carousel__thumbs">
        <button
          v-for="(item, i) in items"
          :key="i"
          type="button"
          class="r-carousel__thumb"
          :class="{ 'r-carousel__thumb--active': i === safeIndex }"
          :aria-label="`${i + 1} / ${total}`"
          :aria-current="i === safeIndex ? 'true' : undefined"
          @click.stop="jumpTo(i)"
        >
          <slot
            name="thumbnail"
            :item="item"
            :index="i"
            :active="i === safeIndex"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-carousel {
  position: relative;
  display: flex;
  flex-direction: column;
  color: var(--r-color-fg);
}

.r-carousel--inline .r-carousel__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.r-carousel__item {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}

/* Fullscreen overlay -------------------------------------------------------- */
.r-carousel--fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  /* Heavy black scrim, slightly translucent so the backdrop hint of motion
     stays visible. CSS named "black" is allowed by the token policy. */
  background: color-mix(in srgb, black 92%, transparent);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: grid;
  grid-template-rows: 1fr auto;
  animation: r-carousel-backdrop-in var(--r-motion-med) var(--r-motion-ease-out);
}

.r-carousel--fullscreen .r-carousel__stage {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 56px 80px;
  overflow: hidden;
}

.r-carousel__item--fullscreen {
  max-width: min(92vw, 1600px);
  max-height: 86vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Pop the active item on first mount with spring easing — the backdrop fade
   is half a beat slower so the item lands on top of an already-darkening
   stage instead of fighting it. */
.r-carousel--fullscreen .r-carousel__item--fullscreen {
  animation: r-carousel-pop var(--r-motion-med) cubic-bezier(0.34, 1.4, 0.64, 1)
    both;
}

.r-carousel--fullscreen :deep(img),
.r-carousel--fullscreen :deep(video) {
  max-width: 100%;
  max-height: 86vh;
  object-fit: contain;
  border-radius: var(--r-radius-md);
  box-shadow: 0 30px 90px color-mix(in srgb, black 80%, transparent);
  display: block;
}

/* Close button ------------------------------------------------------------- */
.r-carousel__close {
  position: absolute;
  top: 18px;
  right: 22px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--r-color-overlay-border);
  border: 1px solid var(--r-color-overlay-border-strong);
  color: var(--r-color-overlay-fg);
  cursor: pointer;
  display: grid;
  place-items: center;
  z-index: 2;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-carousel__close:hover {
  background: var(--r-color-overlay-border-strong);
  transform: scale(1.06);
}
.r-carousel__close:active {
  transform: scale(0.96);
}

/* Nav arrows --------------------------------------------------------------- */
.r-carousel--fullscreen .r-carousel__nav {
  position: absolute;
  top: 50%;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--r-color-overlay-border);
  border: 1px solid var(--r-color-overlay-border-strong);
  color: var(--r-color-overlay-fg);
  display: grid;
  place-items: center;
  cursor: pointer;
  appearance: none;
  z-index: 2;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-carousel--fullscreen .r-carousel__nav:hover:not(:disabled) {
  background: var(--r-color-overlay-border-strong);
  transform: translateY(-50%) scale(1.08);
}
.r-carousel--fullscreen .r-carousel__nav:active:not(:disabled) {
  transform: translateY(-50%) scale(0.96);
}
.r-carousel--fullscreen .r-carousel__nav:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.r-carousel--fullscreen .r-carousel__nav--prev {
  left: 22px;
  transform: translateY(-50%);
}
.r-carousel--fullscreen .r-carousel__nav--next {
  right: 22px;
  transform: translateY(-50%);
}

/* Inline arrows live above the stage — Vuetify-tonal RBtn already handles
   theming, we only need to position them. */
.r-carousel--inline .r-carousel__nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
}
.r-carousel--inline .r-carousel__nav--prev {
  left: 8px;
}
.r-carousel--inline .r-carousel__nav--next {
  right: 8px;
}

/* Counter ------------------------------------------------------------------ */
.r-carousel__counter {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--r-color-overlay-border);
  border: 1px solid var(--r-color-overlay-border-strong);
  color: var(--r-color-overlay-fg);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-medium);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  pointer-events: none;
  user-select: none;
  z-index: 2;
}

/* Fullscreen footer counter: flows in the grid below the thumb strip
   instead of floating over it. The default absolute positioning above
   only applies to the inline variant now. */
.r-carousel__counter--footer {
  position: static;
  transform: none;
  margin: 0 auto 18px;
}

/* Thumbnails --------------------------------------------------------------- */
.r-carousel__thumbs-wrap {
  display: flex;
  justify-content: center;
  padding: 12px 24px 18px;
}
.r-carousel--fullscreen .r-carousel__thumbs-wrap {
  /* When both thumbs and the footer counter are visible, drop the bottom
     padding — the counter brings its own bottom margin. */
  padding-bottom: 6px;
}

.r-carousel__thumbs {
  display: flex;
  gap: 8px;
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  padding: 4px 4px 8px;
  scroll-padding-inline: 24px;
}
.r-carousel__thumbs::-webkit-scrollbar {
  height: 6px;
}
.r-carousel__thumbs::-webkit-scrollbar-thumb {
  background: var(--r-color-overlay-border-strong);
  border-radius: 999px;
}

.r-carousel__thumb {
  flex: 0 0 auto;
  width: 96px;
  height: 56px;
  padding: 0;
  border: 2px solid transparent;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-overlay-border);
  overflow: hidden;
  cursor: pointer;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
  opacity: 0.55;
}
.r-carousel__thumb :deep(img),
.r-carousel__thumb :deep(video) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.r-carousel__thumb:hover {
  opacity: 0.9;
  transform: translateY(-2px);
}
.r-carousel__thumb--active {
  border-color: var(--r-color-brand-primary);
  opacity: 1;
}

/* Transitions -------------------------------------------------------------- */
@keyframes r-carousel-backdrop-in {
  from {
    opacity: 0;
    backdrop-filter: blur(0px);
    -webkit-backdrop-filter: blur(0px);
  }
  to {
    opacity: 1;
  }
}

@keyframes r-carousel-pop {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Direction-aware slide+fade swap. `mode="out-in"` keeps the stack to one
   item at a time — the leaving image animates first, then the arrival
   slides in from the opposite edge. */
.r-carousel-next-leave-active,
.r-carousel-prev-leave-active {
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-carousel-next-enter-active,
.r-carousel-prev-enter-active {
  transition:
    transform var(--r-motion-med) cubic-bezier(0.34, 1.3, 0.64, 1),
    opacity var(--r-motion-med) var(--r-motion-ease-out);
}

.r-carousel-next-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.96);
}
.r-carousel-next-leave-to {
  opacity: 0;
  transform: translateX(-30px) scale(0.98);
}
.r-carousel-prev-enter-from {
  opacity: 0;
  transform: translateX(-40px) scale(0.96);
}
.r-carousel-prev-leave-to {
  opacity: 0;
  transform: translateX(30px) scale(0.98);
}

/* Reduced motion ----------------------------------------------------------- */
@media (prefers-reduced-motion: reduce) {
  .r-carousel--fullscreen,
  .r-carousel--fullscreen .r-carousel__item--fullscreen {
    animation-duration: 1ms;
  }
  .r-carousel-next-enter-active,
  .r-carousel-prev-enter-active,
  .r-carousel-next-leave-active,
  .r-carousel-prev-leave-active {
    transition-duration: 1ms;
  }
}

/* Smaller viewports -------------------------------------------------------- */
@media (max-width: 768px) {
  .r-carousel--fullscreen .r-carousel__stage {
    padding: 56px 16px;
  }
  .r-carousel--fullscreen .r-carousel__nav {
    width: 44px;
    height: 44px;
  }
  .r-carousel--fullscreen .r-carousel__nav--prev {
    left: 8px;
  }
  .r-carousel--fullscreen .r-carousel__nav--next {
    right: 8px;
  }
  .r-carousel__thumb {
    width: 72px;
    height: 42px;
  }
}
</style>
