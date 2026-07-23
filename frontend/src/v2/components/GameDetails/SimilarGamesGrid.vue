<script setup lang="ts">
// SimilarGamesGrid — grid of library games similar to the current ROM.
//
// Unlike RelatedGamesGrid (IGDB related games, which may not be owned and
// need a per-card cross-reference), every entry here is a real library
// ROM ranked by shared metadata. So we render the gallery's GameCard in
// its default mode — it links straight to `/rom/{id}` and carries the
// same platform icon / hover-lift / status chrome as the gallery.
import type { SimpleRom } from "@/stores/roms";
import GameCard from "@/v2/components/GameCard/GameCard.vue";

defineOptions({ inheritAttrs: false });

defineProps<{
  items: SimpleRom[];
}>();
</script>

<template>
  <div v-if="items.length" class="r-v2-similar__grid">
    <GameCard v-for="rom in items" :key="rom.id" :rom="rom" />
  </div>
</template>

<style scoped>
/* Flex-wrap (not auto-fill grid) — GameCard has a fixed 158px width and a
   hard-coded `flex-shrink: 0`, so a `1fr` track would tear the layout on
   narrow viewports. Mirrors RelatedGamesGrid so the two related sections
   read identically. Horizontal padding gives the cover hover-scale room
   before the surrounding scroll container clips it. */
.r-v2-similar__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
  padding: 6px 6px 4px;
}
</style>
