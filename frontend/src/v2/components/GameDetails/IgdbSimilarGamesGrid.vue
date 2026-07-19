<script setup lang="ts">
// IgdbSimilarGamesGrid — IGDB's own "similar games" as a discovery row,
// shown below the library-based list. Any entry already in the library is
// dropped (it's covered by the metadata-based list above), so this row is
// purely external look-up links to games the user doesn't own.
//
// Ownership is resolved with the same IGDB -> RomM cross-reference the
// cards use; the surviving cards are rendered with `force-external` so they
// don't repeat the lookup.
import { computed, ref, watch } from "vue";
import type { IGDBRelatedGame } from "@/__generated__";
import romApi from "@/services/api/rom";
import RelatedGameCard from "@/v2/components/GameDetails/RelatedGameCard.vue";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    items: IGDBRelatedGame[];
    /** Cap on how many unowned suggestions to show. */
    max?: number;
  }>(),
  { max: 6 },
);

const unowned = ref<IGDBRelatedGame[]>([]);
// Monotonic token so a slow ownership resolution from a previous ROM can't
// clobber the current one after a fast navigation.
let token = 0;

watch(
  () => props.items,
  async (items) => {
    const run = ++token;
    if (!items.length) {
      unowned.value = [];
      return;
    }
    const resolved = await Promise.all(
      items.map(async (game) => {
        try {
          await romApi.getRomByMetadataProvider({
            field: "igdb_id",
            id: game.id,
          });
          return null; // In library -> drop.
        } catch {
          return game; // Not found (or lookup denied) -> keep as external.
        }
      }),
    );
    if (run !== token) return;
    unowned.value = resolved.filter((g): g is IGDBRelatedGame => g !== null);
  },
  { immediate: true },
);

const shown = computed(() => unowned.value.slice(0, props.max));
</script>

<template>
  <div v-if="shown.length" class="r-v2-igdb-similar">
    <p class="r-v2-igdb-similar__label">Not in your library</p>
    <div class="r-v2-igdb-similar__grid">
      <RelatedGameCard
        v-for="g in shown"
        :key="g.id"
        :game="g"
        force-external
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-igdb-similar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Quiet sub-label distinguishing the external discovery row from the
   owned/library list above. */
.r-v2-igdb-similar__label {
  margin: 0;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

/* Mirrors RelatedGamesGrid / SimilarGamesGrid so all three read the same:
   flex-wrap over fixed-width GameCards, with padding so the hover-scale
   isn't clipped by the surrounding scroll container. */
.r-v2-igdb-similar__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
  padding: 6px 6px 4px;
}
</style>
