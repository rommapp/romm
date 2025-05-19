<script setup lang="ts">
import Stats from "@/components/Home/Stats.vue";
import PlatformsSize from "@/components/Settings/ServerStats/PlatformsSize.vue";
import api from "@/services/api/index";
import { onBeforeMount, ref } from "vue";

// Props
const stats = ref({
  PLATFORMS_COUNT: 0,
  PLATFORMS: [],
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  TOTAL_FILESIZE: 0,
});

// Functions
onBeforeMount(() => {
  api.get("/stats").then(({ data }) => {
    stats.value = data;
  });
});
</script>
<template>
  <stats class="ma-2" :stats="stats" />
  <platforms-size
    class="ma-2"
    :platforms="stats.PLATFORMS"
    :total="stats.TOTAL_FILESIZE"
  />
</template>
