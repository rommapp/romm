<script setup lang="ts">
import type { UpdateRom } from "@/services/api/rom";
import { parseSceneId, type SceneIdKind } from "@/utils/sceneIds";

const props = defineProps<{ rom: UpdateRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const updateField = (field: keyof UpdateRom, value: string | number | null) => {
  emit("update:rom", { ...props.rom, [field]: value });
};

const parseIdValue = (value: string): number | null => {
  if (!value || value.trim() === "") return null;
  const n = parseInt(value, 10);
  return Number.isNaN(n) ? null : n;
};

const parseSceneIdValue = (
  value: string | null,
  kind: SceneIdKind,
): number | null => parseSceneId(value, kind);
</script>

<template>
  <v-expansion-panel elevation="0">
    <v-expansion-panel-title class="bg-toplayer">
      <v-icon class="mr-2">mdi-database</v-icon>
      Metadata IDs
    </v-expansion-panel-title>
    <v-expansion-panel-text class="mt-4 px-2">
      <v-row no-gutters class="my-2">
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.igdb_id?.toString() || null"
            label="IGDB ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('igdb_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.moby_id?.toString() || null"
            label="MobyGames ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('moby_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.ss_id?.toString() || null"
            label="ScreenScraper ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('ss_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.ra_id?.toString() || null"
            label="RetroAchievements ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('ra_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.launchbox_id?.toString() || null"
            label="LaunchBox ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('launchbox_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.sgdb_id?.toString() || null"
            label="SteamGridDB ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('sgdb_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.hasheous_id?.toString() || null"
            label="Hasheous ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('hasheous_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.flashpoint_id || null"
            label="Flashpoint ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('flashpoint_id', value || null)
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.hltb_id?.toString() || null"
            label="HowLongToBeat ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('hltb_id', parseIdValue(value))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.demozoo_id?.toString() || null"
            label="Demozoo ID"
            variant="outlined"
            @update:model-value="
              (value) =>
                updateField('demozoo_id', parseSceneIdValue(value, 'demozoo'))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.pouet_id?.toString() || null"
            label="Pouët ID"
            variant="outlined"
            @update:model-value="
              (value) =>
                updateField('pouet_id', parseSceneIdValue(value, 'pouet'))
            "
          />
        </v-col>
        <v-col cols="12" md="6" xl="4" class="pa-2">
          <v-text-field
            hide-details
            clearable
            :model-value="rom.csdb_id?.toString() || null"
            label="CSDb ID"
            variant="outlined"
            @update:model-value="
              (value) => updateField('csdb_id', parseSceneIdValue(value, 'csdb'))
            "
          />
        </v-col>
      </v-row>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>
