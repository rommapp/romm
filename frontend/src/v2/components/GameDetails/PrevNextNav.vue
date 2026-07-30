<script setup lang="ts">
// PrevNextNav: step to the previous / next game without going back to
// the gallery.
//
// Order comes from the gallery store's `romIdIndex`, so it always matches
// what the gallery the user came from is showing (search term, filters,
// order-by, grouping). Renders nothing when the current ROM isn't part of
// that list, i.e. a direct link, a related-game jump or a Home row, which
// all land here with no surrounding list to step through.
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  romId: number;
}>();

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const galleryRoms = storeGalleryRoms();

const position = computed(() => galleryRoms.romIdIndex.indexOf(props.romId));

const visible = computed(
  () => position.value >= 0 && galleryRoms.romIdIndex.length > 1,
);

const prevPosition = computed(() =>
  position.value > 0 ? position.value - 1 : null,
);
const nextPosition = computed(() =>
  position.value >= 0 && position.value < galleryRoms.romIdIndex.length - 1
    ? position.value + 1
    : null,
);

// The neighbour's title, when its gallery window happens to be loaded.
// Turns the icon-only buttons into "where am I going" affordances; falls
// back to the generic label whenever the window isn't in cache.
function tooltipFor(position: number | null, fallback: string): string {
  if (position === null) return fallback;
  const rom = galleryRoms.getRomAt(position);
  return rom?.name || rom?.fs_name_no_ext || fallback;
}

const prevTooltip = computed(() =>
  tooltipFor(prevPosition.value, t("rom.previous-game")),
);
const nextTooltip = computed(() =>
  tooltipFor(nextPosition.value, t("rom.next-game")),
);

function go(position: number | null) {
  if (position === null) return;
  router.push({
    name: ROUTES.ROM,
    params: { rom: galleryRoms.romIdIndex[position] },
    // Keep `?tab=` and friends so stepping through a list doesn't drop
    // the user back to Overview on every hop.
    query: route.query,
  });
}
</script>

<template>
  <div v-if="visible" class="prev-next-nav">
    <RBtn
      variant="outlined"
      size="small"
      density="compact"
      icon="mdi-chevron-left"
      :disabled="prevPosition === null"
      :aria-label="t('rom.previous-game')"
      :tooltip="prevTooltip"
      tooltip-location="top"
      @click="go(prevPosition)"
    />
    <RBtn
      variant="outlined"
      size="small"
      density="compact"
      icon="mdi-chevron-right"
      :disabled="nextPosition === null"
      :aria-label="t('rom.next-game')"
      :tooltip="nextTooltip"
      tooltip-location="top"
      @click="go(nextPosition)"
    />
  </div>
</template>

<style scoped>
.prev-next-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
</style>
