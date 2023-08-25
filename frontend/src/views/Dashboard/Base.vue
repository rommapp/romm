<script setup>
import storePlatforms from "@/stores/platforms";
import dashboardSummary from "@/views/Dashboard/Summary.vue"
import dashboardPlatforms from "@/views/Dashboard/Platforms.vue"

// Props
const platforms = storePlatforms();
</script>

<template>
  <!-- Summary -->
  <v-row class="pa-1" no-gutters>
    <v-col>
      <dashboard-summary />
    </v-col>
  </v-row>

  <!-- Platforms -->
  <template v-if="platforms.value.length > 0">
    <v-row class="pa-1" no-gutters>
      <v-col>
        <dashboard-platforms />
      </v-col>
    </v-row>
  </template>
</template>
