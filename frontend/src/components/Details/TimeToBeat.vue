<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { IGDBTimeToBeat } from "@/__generated__/models/IGDBTimeToBeat";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const { t } = useI18n();

const timeToBeat = computed((): IGDBTimeToBeat | null => {
  return props.rom.igdb_metadata?.time_to_beat || null;
});

const hurriedly = computed(() => {
  if (!timeToBeat.value?.hurriedly) return null;
  new Date(timeToBeat.value?.hurriedly).toLocaleDateString("en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
});

const normally = computed(() => {
  if (!timeToBeat.value?.normally) return null;
  new Date(timeToBeat.value?.normally).toLocaleDateString("en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
});

const completely = computed(() => {
  if (!timeToBeat.value?.completely) return null;
  new Date(timeToBeat.value?.completely).toLocaleDateString("en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
});
</script>

<template>
  <div v-if="timeToBeat">
    <v-row class="mb-4">
      <v-col cols="12">
        <h3 class="text-h6 mb-4">{{ t("rom.time-to-beat") }}</h3>
      </v-col>
    </v-row>

    <v-row>
      <v-col v-if="hurriedly" cols="12" sm="4">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.hastily") }}
            </div>
            <div class="text-h5 font-weight-bold">
              {{ hurriedly }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col v-if="normally" cols="12" sm="4">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.normally") }}
            </div>
            <div class="text-h5 font-weight-bold">
              {{ normally }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col v-if="completely" cols="12" sm="4">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.completely") }}
            </div>
            <div class="text-h5 font-weight-bold">
              {{ completely }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row v-if="timeToBeat?.count" class="mt-2">
      <v-col cols="12">
        <div class="text-center text-caption text-medium-emphasis">
          Based on {{ timeToBeat.count }} submission(s)
        </div>
      </v-col>
    </v-row>
  </div>
</template>
