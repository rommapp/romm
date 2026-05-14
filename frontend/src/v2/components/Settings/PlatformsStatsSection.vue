<script setup lang="ts">
// PlatformsStatsSection — v2-native rebuild of v1
// `Settings/ServerStats/PlatformsStats.vue`. Per-platform breakdown
// rows: icon · name + meta (games count, metadata coverage chips,
// region chips with expand/collapse) · size + percentage of total ·
// width-based fill bar at the bottom of each row.
//
// Order-by select sits in the section header so it's reachable
// without scrolling through the list.
import { RIcon, RPlatformIcon, RSelect } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import { formatBytes, regionToEmoji } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  totalFilesize: number;
  metadataCoverage: Record<string, MetadataCoverageItem[]>;
  regionBreakdown: Record<string, RegionBreakdownItem[]>;
}
const props = defineProps<Props>();

const { t } = useI18n();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const heartbeat = storeHeartbeat();

type OrderBy = "name" | "size" | "count";
const orderBy = ref<OrderBy>("name");

const orderItems = [
  { title: "Name", value: "name" },
  { title: "Size", value: "size" },
  { title: "Games", value: "count" },
];

const sortedPlatforms = computed(() => {
  if (orderBy.value === "size") {
    return [...allPlatforms.value].sort(
      (a, b) => Number(b.fs_size_bytes) - Number(a.fs_size_bytes),
    );
  }
  if (orderBy.value === "count") {
    return [...allPlatforms.value].sort((a, b) => b.rom_count - a.rom_count);
  }
  return [...allPlatforms.value].sort((a, b) =>
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
  <SettingsSection :title="t('common.platforms')" icon="mdi-controller">
    <template #header-actions>
      <RSelect
        :model-value="orderBy"
        :items="orderItems"
        density="compact"
        variant="outlined"
        hide-details
        class="r-v2-plat-stats__order"
        @update:model-value="(v) => (orderBy = v as OrderBy)"
      />
    </template>

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
              {{ platform.rom_count }} games
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
                    ? "−"
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
        <div class="r-v2-plat-stats__bar">
          <div
            class="r-v2-plat-stats__bar-fill"
            :style="{ width: platformPercentage(platform.fs_size_bytes) + '%' }"
          />
        </div>
      </div>
      <div v-if="sortedPlatforms.length === 0" class="r-v2-plat-stats__empty">
        <RIcon icon="mdi-folder-question" size="22" />
        <span>No platforms.</span>
      </div>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-plat-stats {
  display: flex;
  flex-direction: column;
}

.r-v2-plat-stats__order {
  width: 140px;
}
.r-v2-plat-stats__order :deep(.r-select__field) {
  font-size: 12px;
}

.r-v2-plat-stats__row {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px 16px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-plat-stats__row:last-child {
  border-bottom: none;
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
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: var(--r-color-border);
  grid-column: 1 / -1;
}
.r-v2-plat-stats__bar-fill {
  height: 100%;
  background: var(--r-color-brand-primary);
  transition: width var(--r-motion-base) var(--r-motion-ease-out);
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
