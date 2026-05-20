<script setup lang="ts">
// ServerStats — v2-native rewrite. Composes the two stat sections
// (Summary + Platforms breakdown). Data fetch is a single /stats call
// with `include_platform_stats=true`; same shape as v1.
import { onBeforeMount, ref } from "vue";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import api from "@/services/api";
import PlatformsStatsSection from "@/v2/components/Settings/PlatformsStatsSection.vue";
import SummaryStatsSection from "@/v2/components/Settings/SummaryStatsSection.vue";

const stats = ref({
  PLATFORMS: 0,
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  TOTAL_FILESIZE_BYTES: 0,
  METADATA_COVERAGE: {} as Record<string, MetadataCoverageItem[]>,
  REGION_BREAKDOWN: {} as Record<string, RegionBreakdownItem[]>,
});

onBeforeMount(() => {
  api
    .get("/stats", { params: { include_platform_stats: true } })
    .then(({ data }) => {
      stats.value = data;
    });
});
</script>

<template>
  <div>
    <SummaryStatsSection :stats="stats" />
    <PlatformsStatsSection
      :total-filesize="stats.TOTAL_FILESIZE_BYTES"
      :metadata-coverage="stats.METADATA_COVERAGE"
      :region-breakdown="stats.REGION_BREAKDOWN"
    />
  </div>
</template>
