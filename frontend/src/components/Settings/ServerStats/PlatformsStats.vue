<script setup lang="ts">
import { storeToRefs } from "pinia";
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RSection from "@/components/common/RSection.vue";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import { formatBytes, platformCategoryToIcon, regionToEmoji } from "@/utils";

const props = defineProps<{
  totalFilesize: number;
  metadataCoverage: Record<string, MetadataCoverageItem[]>;
  regionBreakdown: Record<string, RegionBreakdownItem[]>;
}>();
const { t } = useI18n();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const heartbeat = storeHeartbeat();
const orderBy = ref<"name" | "size" | "count">("name");

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

function getPlatformPercentage(
  filesize: number | string,
  total: number,
): number {
  const size = typeof filesize === "string" ? parseInt(filesize, 10) : filesize;
  if (!total || isNaN(size)) return 0;
  return (size / total) * 100;
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

function getCoveragePercent(matched: number, total: number): string {
  if (!total) return "0";
  return ((matched / total) * 100).toFixed(0);
}
</script>

<template>
  <RSection
    icon="mdi-controller"
    :title="t('common.platforms')"
    elevation="0"
    title-divider
    bg-color="bg-background"
    class="mx-2"
  >
    <template #content>
      <v-row no-gutters>
        <v-col class="pa-4" cols="12">
          <v-select
            v-model="orderBy"
            :items="[
              { title: 'Name', value: 'name' },
              { title: 'Size', value: 'size' },
              { title: 'Count', value: 'count' },
            ]"
            label="Order by"
            variant="outlined"
            hide-details
            density="compact"
          />
        </v-col>
      </v-row>
      <div class="px-4 pb-3">
        <v-sheet
          v-for="platform in sortedPlatforms"
          :key="platform.slug"
          class="overflow-hidden mb-3"
          rounded
        >
          <div class="pa-3">
            <div class="platform-layout grid gap-3">
              <div class="flex items-start pt-1">
                <PlatformIcon
                  :slug="platform.slug"
                  :name="platform.name"
                  :fs-slug="platform.fs_slug"
                  :size="36"
                />
              </div>
              <div class="platform-content">
                <!-- Header: Name + size -->
                <div class="d-flex justify-space-between align-center">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">
                      {{ platform.display_name }}
                    </div>
                    <div class="d-flex align-center ga-1">
                      <v-chip size="x-small" label class="text-grey">
                        {{ platform.fs_slug }}
                      </v-chip>
                      <v-icon
                        :icon="platformCategoryToIcon(platform.category || '')"
                        size="10"
                        class="text-medium-emphasis"
                        :title="platform.category"
                      />
                      <span
                        v-if="platform.family_name"
                        class="text-medium-emphasis"
                        style="font-size: 0.65rem"
                      >
                        {{ platform.family_name }}
                      </span>
                    </div>
                  </div>
                  <div class="text-right shrink-0 ml-4">
                    <div class="text-subtitle-2 font-weight-bold text-primary">
                      {{ formatBytes(Number(platform.fs_size_bytes)) }}
                    </div>
                    <div class="text-medium-emphasis" style="font-size: 0.7rem">
                      {{
                        getPlatformPercentage(
                          platform.fs_size_bytes,
                          props.totalFilesize,
                        ).toFixed(1)
                      }}%
                    </div>
                  </div>
                </div>

                <!-- Detail table: label | value -->
                <div class="detail-table mt-2 flex flex-col gap-2">
                  <div class="detail-row grid items-baseline gap-2">
                    <span
                      class="detail-label whitespace-nowrap font-semibold uppercase opacity-50"
                    >
                      {{ t("setup.games") }}
                    </span>
                    <div>
                      <v-chip size="x-small" label>
                        {{ platform.rom_count }}
                      </v-chip>
                    </div>
                  </div>
                  <div class="detail-row grid items-baseline gap-2">
                    <span
                      class="detail-label whitespace-nowrap font-semibold uppercase opacity-50"
                    >
                      {{ t("rom.metadata") }}
                    </span>
                    <div
                      v-if="
                        orderedCoverageByPlatform[String(platform.id)]?.length >
                        0
                      "
                      class="d-flex flex-wrap ga-1"
                    >
                      <v-chip
                        v-for="item in orderedCoverageByPlatform[
                          String(platform.id)
                        ]"
                        :key="item.source"
                        :title="`${sourceInfo[item.source]?.name ?? item.source}: ${item.matched} / ${platform.rom_count}`"
                        class="min-w-13 justify-center"
                        size="x-small"
                        label
                        variant="tonal"
                      >
                        <v-avatar
                          v-if="sourceInfo[item.source]?.logo_path"
                          start
                          size="12"
                          rounded
                        >
                          <v-img :src="sourceInfo[item.source]?.logo_path" />
                        </v-avatar>
                        {{
                          getCoveragePercent(item.matched, platform.rom_count)
                        }}%
                      </v-chip>
                    </div>
                    <span v-else class="text-xs opacity-25">—</span>
                  </div>
                  <div class="detail-row grid items-baseline gap-2">
                    <span
                      class="detail-label whitespace-nowrap font-semibold uppercase opacity-50"
                    >
                      {{ t("platform.region") }}
                    </span>
                    <div
                      v-if="getVisibleRegions(platform.id).length > 0"
                      class="d-flex flex-wrap ga-1"
                    >
                      <v-chip
                        v-for="item in getVisibleRegions(platform.id)"
                        :key="item.region"
                        :title="`${item.region}: ${item.count}`"
                        class="min-w-13 justify-center"
                        size="x-small"
                        label
                        variant="tonal"
                      >
                        <span class="mr-1">{{
                          regionToEmoji(item.region)
                        }}</span>
                        {{ item.count }}
                      </v-chip>
                      <v-chip
                        v-if="
                          getHiddenRegionCount(platform.id) > 0 ||
                          expandedRegions.has(platform.id)
                        "
                        size="x-small"
                        label
                        variant="text"
                        class="text-medium-emphasis cursor-pointer"
                        @click="toggleRegions(platform.id)"
                      >
                        {{
                          expandedRegions.has(platform.id)
                            ? "−"
                            : "+" + getHiddenRegionCount(platform.id)
                        }}
                      </v-chip>
                    </div>
                    <span v-else class="text-xs opacity-25">—</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="size-bar-track h-0.75">
            <div
              class="size-bar-fill h-full min-w-0 rounded-r-xs duration-300 ease-in-out"
              :style="{
                width:
                  getPlatformPercentage(
                    platform.fs_size_bytes,
                    props.totalFilesize,
                  ) + '%',
              }"
            />
          </div>
        </v-sheet>
      </div>
    </template>
  </RSection>
</template>

<style scoped>
.platform-layout {
  grid-template-columns: 36px 1fr;
}

.detail-table {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.detail-row {
  grid-template-columns: 120px 1fr;
}

.detail-label {
  font-size: 0.625rem;
  line-height: 1.8;
  letter-spacing: 0.04em;
}

.size-bar-track {
  background: rgba(var(--v-border-color), var(--v-border-opacity));
}

.size-bar-fill {
  background: rgb(var(--v-theme-primary));
  transition-property: width;
}
</style>
