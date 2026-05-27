<script setup lang="ts">
// CardRow — horizontal-scrolling section used on the Home dashboard to
// group "Continue playing / Recently added / Favorites / Platforms /
// Collections". Feature composite; Home is the only caller today.
//
// Renders: header (icon + title + count), the default slot as a
// horizontal track, and gradient left/right arrow buttons that appear
// only when the track actually overflows in that direction.
//
// The icon slot sizes to its content — whatever size the caller's inner
// RIcon renders at drives the layout, and the title always stays
// vertically centred with it (flex align-items:center on the head).
import { RBtn, RTag } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

interface Props {
  title?: string;
  count?: number | string;
  /** Horizontal gap between children in the scroll track. */
  gap?: string;
  /** Title font size — defaults to 14.5px. Accepts any CSS length. */
  titleSize?: string | number;
  /**
   * Title font weight — defaults to semibold. Accepts the named weights
   * used elsewhere (regular / medium / semibold / bold) or a raw number.
   */
  titleWeight?: "regular" | "medium" | "semibold" | "bold" | number;
  /** Space between icon and title. Grows naturally as icons get bigger. */
  iconGap?: string;
  /** Icon opacity — default 0.6 keeps it subdued against the title. Set
   *  to 1 when you want the icon to read as prominent as the title. */
  iconOpacity?: number;
}

const props = withDefaults(defineProps<Props>(), {
  title: undefined,
  count: undefined,
  gap: "12px",
  titleSize: "14.5px",
  titleWeight: "semibold",
  iconGap: "10px",
  iconOpacity: 0.6,
});

const resolvedTitleSize = computed(() =>
  typeof props.titleSize === "number"
    ? `${props.titleSize}px`
    : props.titleSize,
);

const WEIGHT_MAP = {
  regular: "var(--r-font-weight-regular)",
  medium: "var(--r-font-weight-medium)",
  semibold: "var(--r-font-weight-semibold)",
  bold: "var(--r-font-weight-bold)",
} as const;

const resolvedTitleWeight = computed(() =>
  typeof props.titleWeight === "number"
    ? `${props.titleWeight}`
    : WEIGHT_MAP[props.titleWeight],
);

const scrollEl = ref<HTMLElement | null>(null);
const canLeft = ref(false);
const canRight = ref(false);

function updateScroll() {
  const el = scrollEl.value;
  if (!el) return;
  canLeft.value = el.scrollLeft > 8;
  canRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 8;
}

function scrollBy(dir: -1 | 1) {
  const el = scrollEl.value;
  if (!el) return;
  el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: "smooth" });
}

// Observe both the track and its children for size changes — covers:
//   * initial mount (track measured before children paint)
//   * skeleton → real card swap (different widths)
//   * window resize collapsing/widening the track
//   * font-load / image-load shifts that change scrollWidth
// Without this, `canRight` is decided once and never reconsidered, so
// rows that overflow only after async data arrives never show the
// right-arrow until the user scrolls manually.
let trackObserver: ResizeObserver | null = null;
let childObserver: MutationObserver | null = null;

function bindObservers() {
  const el = scrollEl.value;
  if (!el) return;
  trackObserver = new ResizeObserver(() => updateScroll());
  trackObserver.observe(el);
  // Observe each child's size too — when a 158px skeleton is replaced
  // by a same-width real card the ResizeObserver on the track itself
  // doesn't always fire (scrollWidth changed but clientWidth didn't),
  // and on the first paint the children may not be present yet.
  for (const child of Array.from(el.children)) {
    trackObserver.observe(child as Element);
  }
  // Re-bind child observation as DOM mutates (skeletons added/removed,
  // real cards inserted).
  childObserver = new MutationObserver(() => {
    if (!trackObserver || !scrollEl.value) return;
    trackObserver.disconnect();
    trackObserver.observe(scrollEl.value);
    for (const child of Array.from(scrollEl.value.children)) {
      trackObserver.observe(child as Element);
    }
    updateScroll();
  });
  childObserver.observe(el, { childList: true });
}

onMounted(() => {
  requestAnimationFrame(updateScroll);
  bindObservers();
});

onBeforeUnmount(() => {
  trackObserver?.disconnect();
  trackObserver = null;
  childObserver?.disconnect();
  childObserver = null;
});
</script>

<template>
  <section class="card-row">
    <header
      v-if="title || $slots.icon || $slots.title"
      class="card-row__head"
      :style="{
        gap: iconGap,
        '--card-row-title-size': resolvedTitleSize,
        '--card-row-title-weight': resolvedTitleWeight,
        '--card-row-icon-opacity': iconOpacity,
      }"
    >
      <span v-if="$slots.icon" class="card-row__icon">
        <slot name="icon" />
      </span>
      <h2 class="card-row__title">
        <slot name="title">
          {{ title }}
        </slot>
      </h2>
      <RTag v-if="count != null" :text="count" size="x-small" />
      <slot name="title-append" />
    </header>

    <div class="card-row__wrap">
      <RBtn
        v-if="canLeft"
        icon="mdi-chevron-left"
        variant="translucent"
        class="card-row__arrow card-row__arrow--left"
        :aria-label="t('common.scroll-left')"
        @click="scrollBy(-1)"
      />
      <RBtn
        v-if="canRight"
        icon="mdi-chevron-right"
        variant="translucent"
        class="card-row__arrow card-row__arrow--right"
        :aria-label="t('common.scroll-right')"
        @click="scrollBy(1)"
      />

      <div
        ref="scrollEl"
        class="card-row__track r-v2-scroll-hidden"
        :style="{ gap }"
        @scroll="updateScroll"
      >
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.card-row {
  margin-bottom: 22px;
}

.card-row__head {
  display: flex;
  align-items: center;
  /* gap is driven inline via the --card-row icon gap prop. */
  padding: 0 var(--r-row-pad);
  margin-bottom: 12px;
  color: var(--r-color-fg-secondary);
}

/* Icon slot — sizes to its content so the caller's RIcon `size` drives
   the layout. Flex align-items:center on the head keeps it vertically
   centred with the title at any icon size. */
.card-row__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: var(--card-row-icon-opacity, 0.6);
  flex-shrink: 0;
  line-height: 0;
}

.card-row__title {
  font-size: var(--card-row-title-size, 14.5px);
  font-weight: var(--card-row-title-weight, var(--r-font-weight-semibold));
  letter-spacing: 0.01em;
  line-height: 1.2;
  margin: 0;
}

.card-row__wrap {
  position: relative;
}

.card-row__track {
  display: flex;
  padding: 16px var(--r-row-pad) 20px;
  overflow-x: auto;
  overflow-y: visible;
  scroll-behavior: smooth;
}

/* Vertically centred, anchored to the row edges. The RBtn surface gets
   a dark scrim so the arrow has contrast over busy cover thumbnails —
   translucent alone reads too faint without a brand color. Override
   RBtn's at-rest opacity (0.7) so the 85% reading comes purely from
   the white-secondary token applied to the icon. */
.card-row__arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
}
.card-row__arrow--left {
  left: 8px;
}
.card-row__arrow--right {
  right: 8px;
}
.card-row__arrow.r-btn {
  background: var(--r-color-overlay-scrim-strong) !important;
  color: var(--r-color-overlay-fg-secondary) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  opacity: 1;
}
.card-row__arrow.r-btn:hover {
  background: color-mix(in srgb, black 88%, transparent) !important;
  color: var(--r-color-overlay-fg) !important;
}

html[data-bp~="xs"] .card-row__track {
  padding: 8px 14px 16px;
}
html[data-bp~="xs"] .card-row__arrow {
  display: none;
}
html[data-bp~="xs"] .card-row__head {
  padding: 0 14px;
}
</style>
