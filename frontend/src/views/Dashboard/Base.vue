<script setup>
import storePlatforms from "@/stores/platforms";
import dashboardSummary from "@/views/Dashboard/Summary.vue";
import recentlyAdded from "@/views/Dashboard/Recent.vue";
import dashboardPlatforms from "@/views/Dashboard/Platforms.vue";

// Props
const platforms = storePlatforms();
</script>

<template>
  <v-row class="pa-1" no-gutters>
    <v-col>
      <dashboard-summary />
    </v-col>
  </v-row>

  <v-row class="pa-1" no-gutters>
    <v-col>
      <recently-added />
    </v-col>
  </v-row>

  <v-row class="pa-1" no-gutters>
    <v-col>
      <dashboard-platforms />
    </v-col>
  </v-row>
</template>
