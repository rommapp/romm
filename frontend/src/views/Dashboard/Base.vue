<script setup lang="ts">
import dashboardSummary from "@/components/Dashboard/Summary.vue";
import recentlyAdded from "@/components/Dashboard/Recent.vue";
import dashboardPlatforms from "@/components/Dashboard/Platforms.vue";

// Props
</script>

<template>
  <v-row class="mx-1 mt-1" no-gutters>
    <v-col>
      <dashboard-summary />
    </v-col>
  </v-row>

  <v-row class="mx-1 mt-1" no-gutters>
    <v-col>
      <recently-added />
    </v-col>
  </v-row>

  <v-row class="mx-1 mt-1" no-gutters>
    <v-col>
      <dashboard-platforms />
    </v-col>
  </v-row>
</template>
