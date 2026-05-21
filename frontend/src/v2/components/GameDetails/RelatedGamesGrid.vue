<script setup lang="ts">
// RelatedGamesGrid — one labelled grid of IGDBRelatedGame tiles.
//
// Used by both the "Additional content" tab (Expansions / DLC) and the
// "Related" tab (Remakes / Remasters / Similar). Multiple sections per
// tab? Render this component multiple times — one per section. Each
// card is a RelatedGameCard, which owns the per-card cross-reference
// against the local RomM library — so this grid stays a thin renderer.
import type { IGDBRelatedGame } from "@/__generated__";
import RelatedGameCard from "@/v2/components/GameDetails/RelatedGameCard.vue";

defineOptions({ inheritAttrs: false });

defineProps<{
  title?: string;
  items: IGDBRelatedGame[];
}>();
</script>

<template>
  <section v-if="items.length" class="r-v2-related">
    <h3 v-if="title" class="r-v2-related__title">
      {{ title }}
    </h3>
    <div class="r-v2-related__grid">
      <RelatedGameCard v-for="g in items" :key="g.id" :game="g" />
    </div>
  </section>
</template>

<style scoped>
.r-v2-related {
  margin-bottom: 24px;
}

.r-v2-related__title {
  margin: 0 0 10px 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

/* Flex-wrap (not auto-fill grid) — GameCard has a fixed 158px width
   and a hard-coded `flex-shrink: 0`, so a `1fr` track would tear the
   layout: the column would compute below 158px on narrow viewports
   and the cards would overflow into the next column. Flex-wrap lets
   each card keep its native width and wrap on the available width
   without inducing a horizontal scrollbar on the overview panel. */
.r-v2-related__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
}
</style>
