<script setup lang="ts">
// LibraryStatsWidget — counts overview of what's in RomM.
//
// Two display modes (driven by `libraryStatsMode` UI setting):
//   • compact  — games / platforms / favorites (3 rows, mock parity)
//   • extended — adds saves / states / screenshots / disk size, the
//                full v1 "Home/Stats" surface, condensed into the
//                widget vocabulary. The card grows wider (not taller)
//                and renders the rows in a 2-column grid so every
//                stat fits inside the rail's shared height.
//
// Source: GET /stats (counts) + the favorite collection's rom_ids
// length (already loaded by the collections store on app boot).
import { RIcon } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import storeCollections from "@/stores/collections";
import { formatBytes } from "@/utils";
import WidgetCard from "./WidgetCard.vue";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    mode?: "compact" | "extended";
  }>(),
  { mode: "compact" },
);

const { t } = useI18n();
const collectionsStore = storeCollections();
const { favoriteCollection } = storeToRefs(collectionsStore);

interface Stats {
  PLATFORMS: number;
  ROMS: number;
  SAVES: number;
  STATES: number;
  SCREENSHOTS: number;
  TOTAL_FILESIZE_BYTES: number;
}

const stats = ref<Stats | null>(null);
const loading = ref(true);

const favoritesCount = computed(
  () => favoriteCollection.value?.rom_ids?.length ?? 0,
);

interface Row {
  icon: string;
  label: string;
  value: string;
}

const allRows = computed<Row[]>(() => {
  const s = stats.value;
  if (!s) return [];
  const base: Row[] = [
    {
      icon: "mdi-disc",
      label: t("common.games"),
      value: s.ROMS.toLocaleString(),
    },
    {
      icon: "mdi-controller",
      label: t("common.platforms"),
      value: s.PLATFORMS.toLocaleString(),
    },
    {
      icon: "mdi-heart",
      label: t("home.widget-library-favorites"),
      value: favoritesCount.value.toLocaleString(),
    },
  ];
  if (props.mode !== "extended") return base;
  return [
    ...base,
    {
      icon: "mdi-content-save",
      label: t("common.saves"),
      value: s.SAVES.toLocaleString(),
    },
    {
      icon: "mdi-file",
      label: t("common.states"),
      value: s.STATES.toLocaleString(),
    },
    {
      icon: "mdi-image-area",
      label: t("home.widget-library-screenshots"),
      value: s.SCREENSHOTS.toLocaleString(),
    },
    {
      icon: "mdi-harddisk",
      label: t("common.size-on-disk"),
      value: formatBytes(s.TOTAL_FILESIZE_BYTES, 1),
    },
  ];
});

onMounted(async () => {
  try {
    const { data } = await api.get<Stats>("/stats");
    stats.value = data;
  } catch {
    stats.value = null;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <WidgetCard
    :title="t('home.widget-library-stats')"
    :loading="loading"
    :width="mode === 'extended' ? 'max-content' : '220px'"
  >
    <div
      class="r-v2-widget-lib__stats"
      :class="{ 'r-v2-widget-lib__stats--multi-col': mode === 'extended' }"
    >
      <div v-for="row in allRows" :key="row.label" class="r-v2-widget-lib__row">
        <span class="r-v2-widget-lib__label">
          <RIcon :icon="row.icon" size="12" />
          {{ row.label }}
        </span>
        <span class="r-v2-widget-lib__val">{{ row.value }}</span>
      </div>
    </div>
  </WidgetCard>
</template>

<style scoped>
.r-v2-widget-lib__stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

/* Extended mode — same card height as compact, but the card itself
   grows wider and the rows lay out in a 3-column grid so all 7 stats
   (3 base + 4 extended) fit in 3 rows inside the shared rail height.
   Columns size to their content (`auto`, paired with the card's
   `max-content` width) so labels never get clipped by large values;
   the rail scrolls horizontally if the numbers get very wide. Column
   gap is generous so the right-aligned values from one column don't
   crowd the left-aligned labels of the next. */
.r-v2-widget-lib__stats--multi-col {
  display: grid;
  grid-template-columns: repeat(3, auto);
  column-gap: 20px;
  row-gap: 6px;
}

.r-v2-widget-lib__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12.5px;
  min-width: 0;
}

.r-v2-widget-lib__label {
  color: var(--r-color-fg-muted);
  display: flex;
  align-items: center;
  gap: 5px;
  /* Grow to fill the (content-sized) column so the value stays pinned
     to the column's right edge across every row. */
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}

.r-v2-widget-lib__val {
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
</style>
