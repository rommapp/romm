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

const intlHours = Intl.NumberFormat("en-US", {
  maximumSignificantDigits: 3,
});
const intlCount = Intl.NumberFormat("en-US");

const mainStory = computed(() => {
  if (!howLongToBeat.value?.main_story) return null;
  // Round to nearest 0.5 hours and divide by 36 centiseconds
  return intlHours.format(
    Math.round((howLongToBeat.value?.main_story / 3600) * 2) / 2,
  );
});
const mainPlusExtra = computed(() => {
  if (!howLongToBeat.value?.main_plus_extra) return null;
  return intlHours.format(
    Math.round((howLongToBeat.value?.main_plus_extra / 3600) * 2) / 2,
  );
});
const completionist = computed(() => {
  if (!howLongToBeat.value?.completionist) return null;
  return intlHours.format(
    Math.round((howLongToBeat.value?.completionist / 3600) * 2) / 2,
  );
});
const allStyles = computed(() => {
  if (!howLongToBeat.value?.all_styles) return null;
  return intlHours.format(
    Math.round((howLongToBeat.value?.all_styles / 3600) * 2) / 2,
  );
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
            <div
              v-if="howLongToBeat.main_story_count"
              class="text-caption text-medium-emphasis mt-1"
            >
              {{ intlCount.format(howLongToBeat.main_story_count) }} players
            </div>
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
            <div
              v-if="howLongToBeat.main_plus_extra_count"
              class="text-caption text-medium-emphasis mt-1"
            >
              {{ intlCount.format(howLongToBeat.main_plus_extra_count) }}
              players
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
            <div
              v-if="howLongToBeat.completionist_count"
              class="text-caption text-medium-emphasis mt-1"
            >
              {{ intlCount.format(howLongToBeat.completionist_count) }} players
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
            <div
              v-if="howLongToBeat.all_styles_count"
              class="text-caption text-medium-emphasis mt-1"
            >
              {{ intlCount.format(howLongToBeat.all_styles_count) }} players
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
