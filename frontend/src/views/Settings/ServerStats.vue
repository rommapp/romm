<script setup lang="ts">
import { onBeforeMount, ref } from "vue";
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
});

onBeforeMount(() => {
  api.get("/stats").then(({ data }) => {
    stats.value = data;
  });
});
</script>
<template>
  <SummaryStats class="ma-2" :stats="stats" />
  <PlatformsStats class="ma-2" :total-filesize="stats.TOTAL_FILESIZE_BYTES" />
</template>
