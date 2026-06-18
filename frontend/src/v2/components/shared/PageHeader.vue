<script setup lang="ts">
// PageHeader — the top-of-page h1 + optional trailing count.
// Used by every index view (PlatformsIndex, CollectionsIndex, Search,
// Settings — future). Pass `count` for the default RTag pill; use the
// `#count` slot when you want richer content (icon, custom tone, etc).
// Default slot sits at the end of the header (filters, actions, etc.).
//
// No divider here — when used as a gallery hero (Search), the gallery
// shell paints the divider between hero and toolbar so the three
// gallery views (Platform / Collection / Search) share one separator
// regardless of which header sits above it.
import { RTag } from "@v2/lib";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    title: string;
    count?: number | string | null;
  }>(),
  { count: null },
);
</script>

<template>
  <header v-bind="$attrs" class="page-header">
    <div class="page-header__title-wrap">
      <h1 class="page-header__title">
        {{ title }}
      </h1>
      <slot name="count">
        <RTag v-if="count != null" :text="count" />
      </slot>
    </div>
    <slot />
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--r-space-3);
  /* Breathing below the title is `padding-bottom` (not margin) so it
     counts in `getBoundingClientRect().height` — the gallery shell
     auto-measures the hero slot to position the toolbar's divider, and
     a margin-bottom would collapse out of that measurement. Visually
     identical for non-gallery consumers (PlatformsIndex etc). */
  padding-bottom: 24px;
}

.page-header__title-wrap {
  display: flex;
  /* Center-align so non-text counts (e.g. RChip in Search) sit on the
     h1's optical centre instead of having their synthesized baseline
     dragged to the title baseline — that misalignment also grew the
     wrap taller than the h1 line-box and shifted the gallery down on
     first paint of the chip. */
  align-items: center;
  gap: 12px;
}

.page-header__title {
  font-size: var(--r-font-size-3xl);
  font-weight: var(--r-font-weight-extrabold);
  letter-spacing: -0.025em;
  color: var(--r-color-fg);
  margin: 0;
  line-height: var(--r-line-height-tight);
}
</style>
