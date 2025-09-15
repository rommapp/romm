<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RomHLTBMetadata } from "@/__generated__/models/RomHLTBMetadata.ts";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const { t } = useI18n();
const howLongToBeat = computed((): RomHLTBMetadata | null => {
  return props.rom.hltb_metadata || null;
});
const mainStory = computed(() => {
  if (!howLongToBeat.value?.main_story) return null;
  return Intl.NumberFormat("en-US", {
    maximumSignificantDigits: 3,
  }).format(howLongToBeat.value?.main_story / 36.5);
});
const mainPlusExtra = computed(() => {
  if (!howLongToBeat.value?.main_plus_extra) return null;
  return Intl.NumberFormat("en-US", {
    maximumSignificantDigits: 3,
  }).format(howLongToBeat.value?.main_plus_extra / 36.5);
});
const completionist = computed(() => {
  if (!howLongToBeat.value?.completionist) return null;
  return Intl.NumberFormat("en-US", {
    maximumSignificantDigits: 3,
  }).format(howLongToBeat.value?.completionist / 36.5);
});
const allStyles = computed(() => {
  if (!howLongToBeat.value?.all_styles) return null;
  return Intl.NumberFormat("en-US", {
    maximumSignificantDigits: 3,
  }).format(howLongToBeat.value?.all_styles / 36.5);
});
</script>

<template>
  <div v-if="howLongToBeat">
    <v-row class="mb-4">
      <v-col cols="12">
        <h3 class="text-h6 mb-4">{{ t("rom.how-long-to-beat") }}</h3>
      </v-col>
    </v-row>

    <v-row>
      <v-col v-if="mainStory" cols="12" sm="6" lg="3">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.main-story") }}
            </div>
            <div class="text-h5 font-weight-bold">{{ mainStory }} Hours</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col v-if="mainPlusExtra" cols="12" sm="6" lg="3">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.main-plus-extra") }}
            </div>
            <div class="text-h5 font-weight-bold">
              {{ mainPlusExtra }} Hours
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col v-if="completionist" cols="12" sm="6" lg="3">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.completionist") }}
            </div>
            <div class="text-h5 font-weight-bold">
              {{ completionist }} Hours
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col v-if="allStyles" cols="12" sm="6" lg="3">
        <v-card>
          <v-card-text class="text-center pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ t("rom.all-styles") }}
            </div>
            <div class="text-h5 font-weight-bold">{{ allStyles }} Hours</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
