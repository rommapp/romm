<script setup lang="ts">
import { formatBytes } from "@/utils";
import RSection from "@/components/common/RSection.vue";
import { useI18n } from "vue-i18n";

defineProps<{
  stats: {
    PLATFORMS: number;
    ROMS: number;
    SAVES: number;
    STATES: number;
    SCREENSHOTS: number;
    TOTAL_FILESIZE_BYTES: number;
  };
}>();
const { t } = useI18n();
</script>

<template>
  <r-section
    icon="mdi-server"
    :title="t('rom.summary')"
    elevation="0"
    titleDivider
    bgColor="bg-background"
    class="mx-2"
  >
    <template #content>
      <v-row class="pa-2" dense>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-controller</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ t("common.platforms-n", stats.PLATFORMS) }}
            </div>
          </v-sheet>
        </v-col>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-disc</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ t("common.games-n", stats.ROMS) }}
            </div>
          </v-sheet>
        </v-col>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-content-save</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ t("common.saves-n", stats.SAVES) }}
            </div>
          </v-sheet>
        </v-col>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-file</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ t("common.states-n", stats.STATES) }}
            </div>
          </v-sheet>
        </v-col>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-image-area</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ t("common.screenshots-n", stats.SCREENSHOTS) }}
            </div>
            <div class="text-caption"></div>
          </v-sheet>
        </v-col>
        <v-col class="pa-2" cols="6" md="4" lg="2">
          <v-sheet class="pa-2 text-center" rounded>
            <v-icon size="32">mdi-harddisk</v-icon>
            <div class="text-h6 text-truncate font-weight-bold">
              {{ formatBytes(stats.TOTAL_FILESIZE_BYTES, 1) }}
              {{ t("common.size-on-disk") }}
            </div>
          </v-sheet>
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
