<script setup lang="ts">
import { onBeforeMount, ref } from "vue";

import { api } from "@/services/api";

const stats = ref({
  PLATFORMS: 0,
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  FILESIZE: 0,
});

onBeforeMount(async () => {
  const { data } = await api.get("/stats");
  stats.value = data;
});
</script>
<template>
  <v-card rounded="0">
    <v-card-text class="py-0 px-2">
      <v-chip-group>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-controller</v-icon
          >{{ stats.PLATFORMS }} Platforms
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ stats.ROMS }} Games
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ stats.SAVES }} Games
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ stats.STATES }} Games
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ stats.SCREENSHOTS }} Games
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ stats.FILESIZE }} Games
        </v-chip>
      </v-chip-group>
    </v-card-text>
  </v-card>
</template>
