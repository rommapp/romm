<script setup lang="ts">
import api from "@/services/api/index";
import { onBeforeMount, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const stats = ref({
  PLATFORMS: 0,
  ROMS: 0,
  SAVES: 0,
  STATES: 0,
  SCREENSHOTS: 0,
  FILESIZE: 0,
});

// Functions
onBeforeMount(() => {
  api.get("/stats").then(({ data }) => {
    stats.value = data;
  });
});
</script>
<template>
  <v-divider />
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
            {{ stats.PLATFORMS }} {{ t("common.platforms") }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-disc"
            variant="text"
            label
          >
            {{ stats.ROMS }} {{ t("common.games") }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-content-save"
            variant="text"
            label
          >
            {{ stats.SAVES }} {{ t("common.saves") }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-file"
            variant="text"
            label
          >
            {{ stats.STATES }} {{ t("common.states") }}
          </v-chip>
        </v-col>
        <v-col>
          <v-chip
            class="text-overline"
            prepend-icon="mdi-image-area"
            variant="text"
            label
          >
            {{ stats.SCREENSHOTS }} {{ t("common.screenshots") }}
          </v-chip>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
