<script setup lang="ts">
import { onBeforeMount, ref } from "vue";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import PlatformsStats from "@/components/Settings/ServerStats/PlatformsStats.vue";
import SummaryStats from "@/components/Settings/ServerStats/SummaryStats.vue";
import api from "@/services/api";

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
  <SummaryStats class="ma-2" :stats="stats" />
  <PlatformsStats
    class="ma-2"
    :total-filesize="stats.TOTAL_FILESIZE_BYTES"
    :metadata-coverage="stats.METADATA_COVERAGE"
    :region-breakdown="stats.REGION_BREAKDOWN"
  />
</template>
