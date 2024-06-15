<script setup lang="ts">
import api from "@/services/api/index";
import { onBeforeMount, ref } from "vue";

const stats = ref({
  PLATFORMS: 0,
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  FILESIZE: 0,
});

onBeforeMount(() => {
  api.get("/stats").then(({ data }) => {
    stats.value = data;
  });
});
</script>
<template>
  <v-card rounded="0">
    <v-card-text class="pa-1">
      <v-row no-gutters class="flex-nowrap overflow-x-auto text-center">
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-controller"
            variant="text"
            label
          >
            {{ stats.PLATFORMS }} Platforms
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-disc"
            variant="text"
            label
          >
            {{ stats.ROMS }} Games
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-content-save"
            variant="text"
            label
          >
            {{ stats.SAVES }} Saves
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-file"
            variant="text"
            label
          >
            {{ stats.STATES }} States
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-image-area"
            variant="text"
            label
          >
            {{ stats.SCREENSHOTS }} Screenshots
          </v-chip>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
