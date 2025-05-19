<script setup lang="ts">
import { formatBytes } from "@/utils";
import { useI18n } from "vue-i18n";

// Props
defineProps<{
  stats: {
    PLATFORMS_COUNT: number;
    ROMS: number;
    SAVES: number;
    STATES: number;
    SCREENSHOTS: number;
    TOTAL_FILESIZE: number;
  };
}>();
const { t } = useI18n();
</script>
<template>
  <v-card>
    <v-card-text class="pa-1">
      <v-row no-gutters class="flex-nowrap overflow-x-auto text-center">
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-controller"
            variant="text"
            label
          >
            {{ t("common.platforms-n", stats.PLATFORMS_COUNT) }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-disc"
            variant="text"
            label
          >
            {{ t("common.games-n", stats.ROMS) }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-content-save"
            variant="text"
            label
          >
            {{ t("common.saves-n", stats.SAVES) }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-file"
            variant="text"
            label
          >
            {{ t("common.states-n", stats.STATES) }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-image-area"
            variant="text"
            label
          >
            {{ t("common.screenshots-n", stats.SCREENSHOTS) }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-harddisk"
            variant="text"
            label
          >
            {{ t("common.size-on-disk") }}:
            {{ formatBytes(stats.TOTAL_FILESIZE, 1) }}
          </v-chip>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
