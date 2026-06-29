<script setup lang="ts">
// CoverColumn — fixed-width left column wrapping the shared GameCover. The
// cover honours the gallery-wide boxart style, animates on hover, paints
// the procedural placeholder when empty, and is the destination of the
// shared-element morph from the GameCard the user clicked through from —
// all of that lives in GameCover now; this just sizes the column.
//
// When the gallery boxart style is the 3D box AND the rom has the full set
// of flat scans (front + back + spine, from ScreenScraper), the hero
// upgrades to the interactive RBox3D the user can spin. Anything missing —
// a different style, an incomplete set, or a failed image — falls straight
// back to the flat GameCover.
import { RBox3D } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import type { DetailedRom } from "@/stores/roms";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBoxFaces } from "@/v2/composables/useBoxFaces";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: DetailedRom;
  alt: string;
}>();

const { t } = useI18n();
const { boxartStyle } = useUISettings();
const faces = useBoxFaces(() => props.rom);
const box3dFailed = ref(false);

// Resolved faces, or null when the interactive box can't / shouldn't render.
// Returning the concrete object keeps the template free of non-null asserts.
const box3d = computed(() => {
  if (boxartStyle.value !== "box3d_path" || box3dFailed.value) return null;
  const f = faces.value;
  if (!f.complete || !f.front || !f.back || !f.spine) return null;
  return { front: f.front, back: f.back, spine: f.spine };
});
</script>

<template>
  <div class="r-v2-det-cover">
    <RBox3D
      v-if="box3d"
      class="r-v2-det-cover__box3d"
      :front="box3d.front"
      :back="box3d.back"
      :spine="box3d.spine"
      :alt="t('rom.box3d-alt', { title: alt })"
      @error="box3dFailed = true"
    />
    <GameCover
      v-else
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

/* Stacked layout (sm-and-down): the cover sits centred above the info
   column at a readable hero size instead of the old ~100px side rail. */
html[data-bp~="sm-and-down"] .r-v2-det-cover {
  width: clamp(120px, 38vw, 200px);
  align-self: center;
  padding-top: 0;
}
</style>
