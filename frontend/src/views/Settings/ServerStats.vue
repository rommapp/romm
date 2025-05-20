<script setup lang="ts">
import SummaryStats from "@/components/Settings/ServerStats/SummaryStats.vue";
import PlatformsStats from "@/components/Settings/ServerStats/PlatformsStats.vue";
import api from "@/services/api/index";
import { onBeforeMount, ref } from "vue";

// Props
const stats = ref({
  PLATFORMS: 0,
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  TOTAL_FILESIZE_BYTES: 0,
});

// Functions
onBeforeMount(() => {
  api.get("/stats").then(({ data }) => {
    stats.value = data;
  });
});
</script>
<template>
  <summary-stats class="ma-2" :stats="stats" />
  <platforms-stats class="ma-2" :total_filesize="stats.TOTAL_FILESIZE_BYTES" />
</template>
