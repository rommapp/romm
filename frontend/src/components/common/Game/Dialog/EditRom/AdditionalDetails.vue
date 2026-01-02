<script setup lang="ts">
import type { UpdateRom } from "@/services/api/rom";

const AGE_RATINGS = [
  {
    system: "ESRB",
    ratings: ["RP", "EC", "E", "E10", "T", "M", "AO"],
  },
  {
    system: "PEGI",
    ratings: ["3", "7", "12", "16", "18"],
  },
  {
    system: "CERO",
    ratings: ["A", "B", "C", "D", "Z"],
  },
  {
    system: "USK",
    ratings: ["0", "6", "12", "16", "18"],
  },
  {
    system: "GRAC",
    ratings: ["All", "12", "15", "18", "Testing"],
  },
  {
    system: "CLASS_IND (Brazil)",
    ratings: ["L", "10", "12", "14", "16", "18"],
  },
  {
    system: "ACB (Australia)",
    ratings: ["G", "PG", "M", "MA15", "R18", "RC"],
  },
].reduce((acc, curr) => {
  curr.ratings.forEach((rating) => {
    acc.push(`${curr.system} - ${rating}`);
  });
  return acc;
}, [] as string[]);

const props = defineProps<{ rom: UpdateRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const udpateManualMetadata = (
  field: keyof UpdateRom["manual_metadata"],
  value: string | number | null,
) => {
  emit("update:rom", {
    ...props.rom,
    manual_metadata: {
      ...props.rom.manual_metadata,
      [field]: value,
    },
  });
};

const manualMetadata = props.rom.manual_metadata || {};
</script>

<template>
  <v-expansion-panel elevation="0">
    <v-expansion-panel-title class="bg-toplayer">
      <v-icon class="mr-2">mdi-text-box-plus</v-icon>
      Additional Details
    </v-expansion-panel-title>
    <v-expansion-panel-text class="mt-4 px-2">
      <v-row no-gutters class="my-2">
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-combobox
            :model-value="manualMetadata.companies || []"
            chips
            multiple
            label="Companies"
            variant="outlined"
            @update:model-value="
              (value) => udpateManualMetadata('companies', value)
            "
          ></v-combobox>
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-combobox
            :model-value="manualMetadata.genres || []"
            chips
            multiple
            label="Genres"
            variant="outlined"
            @update:model-value="
              (value) => udpateManualMetadata('genres', value)
            "
          ></v-combobox>
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-combobox
            :model-value="manualMetadata.franchises || []"
            chips
            multiple
            label="Franchises"
            variant="outlined"
            @update:model-value="
              (value) => udpateManualMetadata('franchises', value)
            "
          ></v-combobox>
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-date-input
            label="Released at"
            variant="outlined"
            prepend-icon=""
            :model-value="
              manualMetadata.first_release_date
                ? new Date(rom.manual_metadata.first_release_date)
                : null
            "
            @update:model-value="
              (value) =>
                udpateManualMetadata(
                  'first_release_date',
                  value && !Number.isNaN(new Date(value).getTime())
                    ? new Date(value).getTime()
                    : null,
                )
            "
          ></v-date-input>
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-combobox
            :model-value="manualMetadata.game_modes || []"
            chips
            multiple
            :items="[
              'Single player',
              'Multiplayer',
              'Co-operative',
              'Split screen',
            ]"
            label="Game Modes"
            variant="outlined"
            @update:model-value="
              (value) => udpateManualMetadata('game_modes', value)
            "
          ></v-combobox>
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="manualMetadata.youtube_video_id || ''"
            label="Youtube Video ID"
            variant="outlined"
            @update:model-value="
              (value) => udpateManualMetadata('youtube_video_id', value)
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-combobox
            :model-value="manualMetadata.age_ratings || []"
            chips
            multiple
            :items="AGE_RATINGS"
            label="Age Ratings"
            variant="outlined"
            @update:model-value="
              (value) =>
                udpateManualMetadata(
                  'age_ratings',
                  value.map((rating) => rating.split(' - ').join(':')),
                )
            "
          ></v-combobox>
        </v-col>
      </v-row>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>
