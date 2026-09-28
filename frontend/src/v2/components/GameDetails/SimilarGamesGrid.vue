<script setup lang="ts">
// The "Similar games" section of the overview tab. Every entry is a real ROM
// resolved server-side, so unlike RelatedGamesGrid these are ordinary
// interactive GameCards with no per-card library lookup.
import type { SimilarRomSchema } from "@/__generated__";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import RecommendationReason from "@/v2/components/shared/RecommendationReason.vue";

defineOptions({ inheritAttrs: false });

defineProps<{
  items: SimilarRomSchema[];
  webp?: boolean;
}>();
</script>

<template>
  <div class="similar-games">
    <div
      v-for="item in items"
      :key="`sim-${item.rom.id}`"
      class="similar-games__item"
    >
      <GameCard :rom="item.rom" :webp="webp" />
      <RecommendationReason :reasons="item.reasons" />
    </div>
  </div>
</template>

<style scoped>
/* Flex-wrap rather than an auto-fill grid: GameCard has a fixed width and
   never shrinks, so a `1fr` track overflows on narrow viewports. The padding
   leaves room for the cover hover-scale before the scroll container clips it. */
.similar-games {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
  padding: 6px 6px 4px;
}

.similar-games__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
