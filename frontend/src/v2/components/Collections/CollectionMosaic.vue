<script setup lang="ts">
// CollectionMosaic — 2×2 cover grid for collection artwork. Feature
// component used by CollectionTile and the collection info panel.
// Behaviour:
//   * 0 covers → empty state with a bookmark glyph
//   * 1 cover  → fills the whole tile
//   * 2-3 covers → 2x2 grid, covers cycle to fill the 4 slots so the
//     mosaic never shows an empty square
//   * 4+ covers → 2x2 grid using the first 4
// Default aspect is portrait (140/188, same ratio game covers use) so
// collection artwork reads as cover-art, not a square thumbnail.
import { RIcon } from "@v2/lib";
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  covers?: (string | null | undefined)[];
  aspectRatio?: string;
  radius?: string;
}

const props = withDefaults(defineProps<Props>(), {
  covers: () => [],
  aspectRatio: "140 / 188",
  radius: "var(--r-radius-lg)",
});

const displayCovers = computed(() =>
  (props.covers ?? []).filter((c): c is string => Boolean(c)),
);

// Mosaic slots — if we have 2 or 3 covers, cycle through them so every
// slot is filled. Deterministic (index % len) instead of random so the
// mosaic doesn't shuffle between re-renders.
const mosaicSlots = computed(() => {
  const src = displayCovers.value;
  if (src.length === 0) return [];
  return Array.from({ length: 4 }, (_, i) => src[i % src.length]);
});
</script>

<template>
  <div
    class="coll-mosaic"
    :class="{ 'coll-mosaic--single': displayCovers.length <= 1 }"
    :style="{ aspectRatio, borderRadius: radius }"
  >
    <template v-if="!displayCovers.length">
      <div class="coll-mosaic__empty">
        <RIcon icon="mdi-bookmark-outline" size="20" />
      </div>
    </template>
    <template v-else-if="displayCovers.length === 1">
      <img :src="displayCovers[0] ?? undefined" alt="" />
    </template>
    <template v-else>
      <img
        v-for="(cover, i) in mosaicSlots"
        :key="`m-${i}`"
        :src="cover"
        alt=""
      />
    </template>
  </div>
</template>

<style scoped>
.coll-mosaic {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  overflow: hidden;
  background: var(--r-color-bg-elevated);
  width: 100%;
}

.coll-mosaic--single {
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
}

.coll-mosaic img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.coll-mosaic__empty {
  grid-column: 1 / -1;
  grid-row: 1 / -1;
  display: grid;
  place-items: center;
  color: var(--r-color-fg-faint);
}
</style>
