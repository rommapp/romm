<script setup lang="ts">
// GameCardSkeleton — placeholder rendered for un-fetched gallery slots
// and for the Home dashboard's loading rows.
//
// Geometry mirrors GameCard exactly (default and hero) so the
// virtualiser's measurements stay stable when a window fetch resolves
// and skeletons swap for real cards — without that match the
// virtualiser re-measures total height and the scroll position jitters
// on every fetch. Same reasoning applies on Home: the loading row's
// shape must match the cards that replace it so the layout doesn't
// jump when data arrives.
//
// Sizing is passed via props (not CSS classes) because RSkeletonBlock
// renders its width/height as inline styles, and inline styles win
// over scoped class CSS — so a `.r-gcs__art { height: ... }` rule
// would be ignored. The CSS vars resolve at render time, so the
// skeleton still picks up theme/density token changes automatically.
import { RSkeletonBlock } from "@v2/lib";
import { computed } from "vue";

interface Props {
  /** Hero variant — 16:9 art with a larger label, matching `GameCard`'s
   *  `hero` prop. Scales with `size` (same as GameCard). */
  hero?: boolean;
  /** Size tier — mirrors `GameCard`'s `size` prop so a skeleton swapped
   *  into a tiered card slot keeps the same footprint and the
   *  virtualiser's measurements stay stable. */
  size?: "xs" | "sm" | "md" | "lg" | "xl";
}

const props = withDefaults(defineProps<Props>(), { hero: false, size: "md" });

const artWidth = computed(() =>
  props.hero ? "var(--r-hero-w)" : "var(--r-card-art-w)",
);
const artHeight = computed(() =>
  props.hero ? "var(--r-hero-h)" : "var(--r-card-art-h)",
);
</script>

<template>
  <div
    class="r-gcs"
    :class="[
      size !== 'md' && `r-gcs--size-${size}`,
      { 'r-gcs--hero': hero },
    ]"
  >
    <RSkeletonBlock
      :width="artWidth"
      :height="artHeight"
      :rounded="hero ? 'lg' : 'md'"
    />
    <RSkeletonBlock class="r-gcs__label" width="60%" :height="hero ? 14 : 11" />
  </div>
</template>

<style scoped>
.r-gcs {
  width: var(--r-card-art-w);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.r-gcs__label {
  /* Match GameCard's `.r-gc__label`: margin-top 7px, font-size 11.5px,
     line-height ~16px → reserve ~16px so total card+label height lines
     up to the same number of pixels regardless of which slot kind
     renders. */
  margin-top: 7px !important;
  height: 16px;
}

/* Hero (16:9) variant — mirrors `GameCard`'s `.r-gc--hero` block. The
   art skeleton picks up its own larger size via the prop-bound CSS
   vars; here we just widen the container so the centred label sits at
   the right horizontal width, and bump the label's reserved height to
   match the hero label's 13px font. */
.r-gcs--hero {
  width: var(--r-hero-w);
}
.r-gcs--hero .r-gcs__label {
  height: 18px;
}

/* Size tiers — mirror GameCard's `.r-gc--size-*` overrides exactly so
   skeleton + real card occupy the same footprint when one swaps for
   the other in a virtualiser slot. */
.r-gcs--size-xs {
  --r-card-art-w: var(--r-card-art-w-xs);
  --r-card-art-h: var(--r-card-art-h-xs);
  --r-hero-w: var(--r-hero-w-xs);
  --r-hero-h: var(--r-hero-h-xs);
}
.r-gcs--size-sm {
  --r-card-art-w: var(--r-card-art-w-sm);
  --r-card-art-h: var(--r-card-art-h-sm);
  --r-hero-w: var(--r-hero-w-sm);
  --r-hero-h: var(--r-hero-h-sm);
}
.r-gcs--size-lg {
  --r-card-art-w: var(--r-card-art-w-lg);
  --r-card-art-h: var(--r-card-art-h-lg);
  --r-hero-w: var(--r-hero-w-lg);
  --r-hero-h: var(--r-hero-h-lg);
}
.r-gcs--size-xl {
  --r-card-art-w: var(--r-card-art-w-xl);
  --r-card-art-h: var(--r-card-art-h-xl);
  --r-hero-w: var(--r-hero-w-xl);
  --r-hero-h: var(--r-hero-h-xl);
}
</style>
