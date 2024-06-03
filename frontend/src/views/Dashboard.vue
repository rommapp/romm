<script setup lang="ts">
import dashboardPlatforms from "@/components/Dashboard/Platforms.vue";
import recentlyAdded from "@/components/Dashboard/Recent.vue";
import dashboardSummary from "@/components/Dashboard/Summary.vue";
</script>

<template>
  <v-row
    class="mx-1 mt-1"
    no-gutters
  >
    <v-col>
      <dashboard-summary />
    </v-col>
  </v-row>

  <v-row
    class="mx-1 mt-1"
    no-gutters
  >
    <v-col>
      <recently-added />
    </v-col>
  </v-row>

  <v-row
    class="mx-1 mt-1"
    no-gutters
  >
    <v-col>
      <dashboard-platforms />
    </v-col>
  </v-row>
</template>
