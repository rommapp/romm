<script setup lang="ts">
// PlatformsStatsSection — v2-native rebuild of v1
// `Settings/ServerStats/PlatformsStats.vue`. Per-platform breakdown
// rows: icon · name + meta (games count, metadata coverage chips,
// region chips with expand/collapse) · size + percentage of total ·
// progress bar that doubles as the row divider.
//
// Toolbar mirrors GalleryToolbar's pattern: inline-prefix search on
// the left, icon-only segmented sort on the right. No card chrome —
// this section sits flush in the page; only the Summary section above
// keeps a surface.
import {
  RIcon,
  RPlatformIcon,
  RProgressLinear,
  RSliderBtnGroup,
  RTextField,
} from "@v2/lib";
import type { SliderBtnGroupItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import { formatBytes, regionToEmoji } from "@/utils";

defineOptions({ inheritAttrs: false });

interface Props {
  totalFilesize: number;
  metadataCoverage: Record<string, MetadataCoverageItem[]>;
  regionBreakdown: Record<string, RegionBreakdownItem[]>;
}
const props = defineProps<Props>();

const { t } = useI18n();
const platformsStore = storePlatforms();
// Only platforms that still contain games, matching the Platforms page, the
// Home screen, and this page's own summary counter. Empty leftovers (0-game
// platforms kept in the DB) are hidden everywhere else, so exclude them here
// too instead of leaking through the raw list.
const { filledPlatforms } = storeToRefs(platformsStore);
const heartbeat = storeHeartbeat();

type OrderBy = "name" | "size" | "count";
const orderBy = ref<OrderBy>("name");
const searchQuery = ref("");

const orderItems = computed<SliderBtnGroupItem<OrderBy>[]>(() => [
  {
    id: "name",
    icon: "mdi-sort-alphabetical-variant",
    ariaLabel: t("settings.sort-by-name"),
    title: t("settings.sort-name"),
  },
  {
    id: "size",
    icon: "mdi-harddisk",
    ariaLabel: t("settings.sort-by-size"),
    title: t("settings.sort-size"),
  },
  {
    id: "count",
    icon: "mdi-numeric",
    ariaLabel: t("settings.sort-by-game-count"),
    title: t("settings.sort-games"),
  },
]);

const sortedPlatforms = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  let list = [...filledPlatforms.value];
  if (q) {
    list = list.filter(
      (p) =>
        p.display_name.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q),
    );
  }
  if (orderBy.value === "size") {
    return list.sort(
      (a, b) => Number(b.fs_size_bytes) - Number(a.fs_size_bytes),
    );
  }
  if (orderBy.value === "count") {
    return list.sort((a, b) => b.rom_count - a.rom_count);
  }
  return list.sort((a, b) =>
    a.display_name.localeCompare(b.display_name, undefined, {
      sensitivity: "base",
    }),
  );
});

const metadataOptions = computed(() =>
  heartbeat.getMetadataOptionsByPriority(),
);

const sourceInfo = computed(() => {
  const map: Record<string, { name: string; logo_path: string }> = {};
  for (const opt of metadataOptions.value) {
    map[opt.value] = { name: opt.name, logo_path: opt.logo_path };
  }
  return map;
});

const orderedCoverageByPlatform = computed(() => {
  const priority = metadataOptions.value.map((o) => o.value);
  const result: Record<string, MetadataCoverageItem[]> = {};
  for (const [id, items] of Object.entries(props.metadataCoverage)) {
    result[id] = [...items].sort(
      (a, b) => priority.indexOf(a.source) - priority.indexOf(b.source),
    );
  }
  return result;
});

function platformPercentage(filesize: number | string): number {
  const size = typeof filesize === "string" ? parseInt(filesize, 10) : filesize;
  if (!props.totalFilesize || isNaN(size)) return 0;
  return (size / props.totalFilesize) * 100;
}

const MAX_VISIBLE_REGIONS = 5;
const expandedRegions = ref(new Set<number>());

function getVisibleRegions(platformId: number): RegionBreakdownItem[] {
  const items = props.regionBreakdown[String(platformId)];
  if (!items) return [];
  if (expandedRegions.value.has(platformId)) return items;
  return items.slice(0, MAX_VISIBLE_REGIONS);
}

function getHiddenRegionCount(platformId: number): number {
  if (expandedRegions.value.has(platformId)) return 0;
  const items = props.regionBreakdown[String(platformId)];
  if (!items) return 0;
  return Math.max(0, items.length - MAX_VISIBLE_REGIONS);
}

function toggleRegions(platformId: number): void {
  const s = new Set(expandedRegions.value);
  if (s.has(platformId)) s.delete(platformId);
  else s.add(platformId);
  expandedRegions.value = s;
}

function coveragePercent(matched: number, total: number): string {
  if (!total) return "0";
  return ((matched / total) * 100).toFixed(0);
}
</script>

<template>
  <section class="r-v2-plat-stats-section">
    <div class="r-v2-plat-stats__toolbar">
      <RTextField
        :model-value="searchQuery"
        :placeholder="t('settings.search-platforms')"
        density="comfortable"
        prefix-label="inline"
        clearable
        hide-details
        class="r-v2-plat-stats__search"
        @update:model-value="(v) => (searchQuery = (v as string) ?? '')"
      >
        <template #prefix-label>
          <RIcon icon="mdi-magnify" size="16" />
        </template>
      </RTextField>
      <RSliderBtnGroup
        :model-value="orderBy"
        :items="orderItems"
        variant="segmented"
        :aria-label="t('settings.order-platforms-by')"
        class="r-v2-plat-stats__order"
        @update:model-value="(v) => (orderBy = v)"
      />
    </div>

    <div class="r-v2-plat-stats">
      <div
        v-for="platform in sortedPlatforms"
        :key="platform.slug"
        class="r-v2-plat-stats__row"
      >
        <RPlatformIcon
          :slug="platform.slug"
          :name="platform.name"
          :fs-slug="platform.fs_slug"
          :size="32"
          class="r-v2-plat-stats__icon"
        />
        <div class="r-v2-plat-stats__info">
          <div class="r-v2-plat-stats__name">
            {{ platform.display_name }}
          </div>
          <div class="r-v2-plat-stats__meta">
            <span class="r-v2-plat-stats__count">
              {{
                t("settings.platform-count-games", {
                  count: platform.rom_count,
                })
              }}
            </span>
            <template
              v-if="orderedCoverageByPlatform[String(platform.id)]?.length > 0"
            >
              <span class="r-v2-plat-stats__sep">·</span>
              <span
                v-for="item in orderedCoverageByPlatform[String(platform.id)]"
                :key="item.source"
                class="r-v2-plat-stats__coverage"
                :title="`${sourceInfo[item.source]?.name ?? item.source}: ${item.matched} / ${platform.rom_count}`"
              >
                <img
                  v-if="sourceInfo[item.source]?.logo_path"
                  :src="sourceInfo[item.source]?.logo_path"
                  class="r-v2-plat-stats__coverage-logo"
                  alt=""
                />
                {{ coveragePercent(item.matched, platform.rom_count) }}%
              </span>
            </template>
            <template v-if="getVisibleRegions(platform.id).length > 0">
              <span class="r-v2-plat-stats__sep">·</span>
              <span
                v-for="r in getVisibleRegions(platform.id)"
                :key="r.region"
                class="r-v2-plat-stats__region"
                :title="`${r.region}: ${r.count}`"
              >
                {{ regionToEmoji(r.region) }} {{ r.count }}
              </span>
              <button
                v-if="
                  getHiddenRegionCount(platform.id) > 0 ||
                  expandedRegions.has(platform.id)
                "
                type="button"
                class="r-v2-plat-stats__more"
                @click="toggleRegions(platform.id)"
              >
                {{
                  expandedRegions.has(platform.id)
                    ? "-"
                    : "+" + getHiddenRegionCount(platform.id)
                }}
              </button>
            </template>
          </div>
        </div>
        <div class="r-v2-plat-stats__size">
          <div class="r-v2-plat-stats__size-value">
            {{ formatBytes(Number(platform.fs_size_bytes)) }}
          </div>
          <div class="r-v2-plat-stats__size-pct">
            {{ platformPercentage(platform.fs_size_bytes).toFixed(1) }}%
          </div>
        </div>
        <RProgressLinear
          :model-value="platformPercentage(platform.fs_size_bytes)"
          :height="3"
          :rounded="false"
          color="primary"
          class="r-v2-plat-stats__bar"
        />
      </div>
      <div v-if="sortedPlatforms.length === 0" class="r-v2-plat-stats__empty">
        <RIcon icon="mdi-folder-question" size="22" />
        <span>{{
          searchQuery.trim()
            ? t("settings.no-matching-platforms")
            : t("settings.no-platforms")
        }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-v2-plat-stats-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.r-v2-plat-stats__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Search width mirrors GalleryToolbar — bounded so the sort cluster
   stays comfortably visible on wide screens but the field collapses
   gracefully when the panel narrows. */
.r-v2-plat-stats__search {
  flex: 0 1 360px;
  min-width: 0;
}

.r-v2-plat-stats__order {
  margin-left: auto;
}

.r-v2-plat-stats {
  display: flex;
  flex-direction: column;
}

.r-v2-plat-stats__row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  column-gap: 14px;
  row-gap: 12px;
  align-items: center;
  padding-top: 14px;
}
.r-v2-plat-stats__row:first-child {
  padding-top: 0;
}

.r-v2-plat-stats__icon {
  flex-shrink: 0;
}

.r-v2-plat-stats__info {
  min-width: 0;
}
.r-v2-plat-stats__name {
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-plat-stats__meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-plat-stats__count {
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-plat-stats__sep {
  color: var(--r-color-fg-faint);
}

.r-v2-plat-stats__coverage,
.r-v2-plat-stats__region {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}

.r-v2-plat-stats__coverage-logo {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  object-fit: cover;
}

.r-v2-plat-stats__more {
  border: none;
  background: transparent;
  color: var(--r-color-fg-faint);
  font-size: 11px;
  cursor: pointer;
  padding: 1px 6px;
}
.r-v2-plat-stats__more:hover {
  color: var(--r-color-fg);
}

.r-v2-plat-stats__size {
  text-align: right;
  flex-shrink: 0;
}
.r-v2-plat-stats__size-value {
  font-size: 13px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-brand-primary);
  font-variant-numeric: tabular-nums;
}
.r-v2-plat-stats__size-pct {
  font-size: 11px;
  color: var(--r-color-fg-faint);
}

.r-v2-plat-stats__bar {
  grid-column: 1 / -1;
}

.r-v2-plat-stats__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--r-color-fg-muted);
}
</style>
