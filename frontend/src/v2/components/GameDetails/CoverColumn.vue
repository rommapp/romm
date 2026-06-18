<script setup lang="ts">
// CoverColumn — fixed-width left column wrapping the shared GameCover. The
// cover honours the gallery-wide boxart style, animates on hover, paints
// the procedural placeholder when empty, and is the destination of the
// shared-element morph from the GameCard the user clicked through from —
// all of that lives in GameCover now; this just sizes the column.
import type { DetailedRom } from "@/stores/roms";
import GameCover from "@/v2/components/shared/GameCover.vue";

defineOptions({ inheritAttrs: false });

defineProps<{
  rom: DetailedRom;
  alt: string;
}>();
</script>

<template>
  <div class="r-v2-det-cover">
    <GameCover
      class="r-v2-det-cover__art"
      :rom="rom"
      :title="alt"
      :identified="rom.is_identified"
      :morph-id="rom.id"
      morph-static
      hover-motion
    />
  </div>
</template>

<style scoped>
.r-v2-det-cover {
  flex-shrink: 0;
  align-self: flex-start;
  /* No sticky needed: GameDetails fits the main viewport exactly and only
     the inner tab panel scrolls. */
  padding-top: 40px;
  width: var(--r-cover-w);
}
/* Larger radius than the gallery card (this is the hero cover). */
.r-v2-det-cover__art {
  --r-cover-radius: var(--r-radius-lg);
}

html[data-bp~="xs"] .r-v2-det-cover {
  width: 100px;
  margin-top: 0;
}
</style>
