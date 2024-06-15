<script setup lang="ts">
import dashboardPlatforms from "@/layouts/Dashboard/Platforms.vue";
import recentlyAdded from "@/layouts/Dashboard/Recent.vue";
import dashboardSummary from "@/layouts/Dashboard/Summary.vue";
</script>

<template>
  <dashboard-summary />
  <recently-added />
  <dashboard-platforms />
</template>
