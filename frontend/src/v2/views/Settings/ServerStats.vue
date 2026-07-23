<script setup lang="ts">
// ServerStats — v2-native rewrite. Composes the two stat sections
// (Summary + Platforms breakdown). The summary is fetched on its own first
// so the six cards paint immediately; the heavier per-platform breakdown
// loads as a second request.
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

onBeforeMount(async () => {
  // The six summary cards are cheap to compute, so load them first and let
  // them render right away rather than waiting on the breakdown's queries.
  const { data: summary } = await api.get("/stats");
  stats.value = { ...stats.value, ...summary };

  // The per-platform breakdown runs the heavier queries; fetch it separately
  // and merge it in when it arrives. A failure here leaves the summary cards
  // and platform rows usable, so degrade to partial data instead of rejecting
  // the hook with an uncaught error.
  try {
    const { data: full } = await api.get("/stats", {
      params: { include_platform_stats: true },
    });
    stats.value = {
      ...stats.value,
      METADATA_COVERAGE: full.METADATA_COVERAGE,
      REGION_BREAKDOWN: full.REGION_BREAKDOWN,
    };
  } catch (error) {
    console.error("Failed to load Server Stats breakdown:", error);
  }
});
</script>

<template>
  <div class="r-v2-section-stack">
    <SummaryStatsSection :stats="stats" />
    <PlatformsStatsSection
      :total-filesize="stats.TOTAL_FILESIZE_BYTES"
      :metadata-coverage="stats.METADATA_COVERAGE"
      :region-breakdown="stats.REGION_BREAKDOWN"
    />
  </div>
</template>
