<script setup lang="ts">
// AdditionalDetails (v2): manual metadata overrides for the edit-ROM
// dialog.
//
// All writes go through `manual_metadata`: the backend layer where
// admins override automatic scraper output. Emitting `update:rom` with
// the merged shape keeps the parent in charge of when to actually
// commit (Save button on EditRomDialog).
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RComboboxField, RDateField, RTextField } from "@/lib";
import MetadataLockControl from "@/components/EditRom/MetadataLockControl.vue";
import type { MetadataLockField, UpdateRom } from "@/services/api/rom";

const props = defineProps<{
  rom: UpdateRom;
  metadataLockedFields: string[];
  metadataLockDisabled: boolean;
}>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
  "toggle-metadata-lock": [field: MetadataLockField];
}>();

const { t } = useI18n();

// Age-rating items are pre-built once from the rating systems we
// surface. Stored as "SYSTEM:RATING" so a single string captures both
// halves; the combobox shows "SYSTEM - RATING" for legibility and the
// commit step translates back to the colon form the backend expects.
const AGE_RATING_SYSTEMS: { system: string; ratings: string[] }[] = [
  { system: "ESRB", ratings: ["RP", "EC", "E", "E10", "T", "M", "AO"] },
  { system: "PEGI", ratings: ["3", "7", "12", "16", "18"] },
  { system: "CERO", ratings: ["A", "B", "C", "D", "Z"] },
  { system: "USK", ratings: ["0", "6", "12", "16", "18"] },
  { system: "GRAC", ratings: ["All", "12", "15", "18", "Testing"] },
  {
    system: "CLASS_IND (Brazil)",
    ratings: ["L", "10", "12", "14", "16", "18"],
  },
  {
    system: "ACB (Australia)",
    ratings: ["G", "PG", "M", "MA15", "R18", "RC"],
  },
];

const AGE_RATING_ITEMS = AGE_RATING_SYSTEMS.flatMap(({ system, ratings }) =>
  ratings.map((r) => `${system} - ${r}`),
);

const GAME_MODE_ITEMS = computed(() => [
  t("rom.game-mode-single-player"),
  t("rom.game-mode-multiplayer"),
  t("rom.game-mode-co-operative"),
  t("rom.game-mode-split-screen"),
]);

const manual = computed(() => props.rom.manual_metadata || {});

// Age ratings are stored as `SYSTEM:RATING` strings: convert to the
// human-readable `SYSTEM - RATING` shape the combobox uses, and back.
const ageRatingsView = computed(() =>
  (manual.value.age_ratings ?? []).map((r) => r.replace(":", " - ")),
);

function updateManualMetadata(
  field: keyof NonNullable<UpdateRom["manual_metadata"]>,
  value: string | number | string[] | null,
) {
  emit("update:rom", {
    ...props.rom,
    manual_metadata: {
      ...props.rom.manual_metadata,
      [field]: value,
    },
  });
}
</script>

<template>
  <div class="r-additional">
    <RComboboxField
      :model-value="manual.alternative_names ?? []"
      :label="t('rom.alternative-titles')"
      prefix-label="stacked"
      variant="outlined"
      density="comfortable"
      allow-commas
      clearable
      @update:model-value="(v) => updateManualMetadata('alternative_names', v)"
    />
    <div class="r-additional__lockable">
      <RComboboxField
        :model-value="manual.companies ?? []"
        :label="t('rom.companies')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(v) => updateManualMetadata('companies', v)"
      />
      <MetadataLockControl
        field="companies"
        :label="t('rom.companies')"
        :locked="metadataLockedFields.includes('companies')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <RComboboxField
      :model-value="manual.publishers ?? []"
      :label="t('rom.publishers')"
      prefix-label="stacked"
      variant="outlined"
      density="comfortable"
      clearable
      @update:model-value="(v) => updateManualMetadata('publishers', v)"
    />
    <RComboboxField
      :model-value="manual.developers ?? []"
      :label="t('rom.developers')"
      prefix-label="stacked"
      variant="outlined"
      density="comfortable"
      clearable
      @update:model-value="(v) => updateManualMetadata('developers', v)"
    />
    <div class="r-additional__lockable">
      <RComboboxField
        :model-value="manual.genres ?? []"
        :label="t('rom.genres')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(v) => updateManualMetadata('genres', v)"
      />
      <MetadataLockControl
        field="genres"
        :label="t('rom.genres')"
        :locked="metadataLockedFields.includes('genres')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <div class="r-additional__lockable">
      <RTextField
        :model-value="(rom.metadatum.collections ?? []).join(', ')"
        :label="t('rom.collections')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        hide-details
        readonly
      />
      <MetadataLockControl
        field="collections"
        :label="t('rom.collections')"
        :locked="metadataLockedFields.includes('collections')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <div class="r-additional__lockable">
      <RComboboxField
        :model-value="manual.franchises ?? []"
        :label="t('rom.franchises')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(v) => updateManualMetadata('franchises', v)"
      />
      <MetadataLockControl
        field="franchises"
        :label="t('rom.franchises')"
        :locked="metadataLockedFields.includes('franchises')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <div class="r-additional__lockable">
      <RDateField
        :model-value="manual.first_release_date ?? null"
        :label="t('rom.released-at')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="
          (d) =>
            updateManualMetadata('first_release_date', d ? d.getTime() : null)
        "
      />
      <MetadataLockControl
        field="first_release_date"
        :label="t('rom.released-at')"
        :locked="metadataLockedFields.includes('first_release_date')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <div class="r-additional__lockable">
      <RComboboxField
        :model-value="manual.game_modes ?? []"
        :items="GAME_MODE_ITEMS"
        :label="t('rom.game-modes')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(v) => updateManualMetadata('game_modes', v)"
      />
      <MetadataLockControl
        field="game_modes"
        :label="t('rom.game-modes')"
        :locked="metadataLockedFields.includes('game_modes')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <div class="r-additional__lockable">
      <RTextField
        :model-value="rom.metadatum.player_count ?? ''"
        :label="t('rom.player-count')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        hide-details
        readonly
      />
      <MetadataLockControl
        field="player_count"
        :label="t('rom.player-count')"
        :locked="metadataLockedFields.includes('player_count')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
    <RTextField
      :model-value="manual.youtube_video_id ?? ''"
      :label="t('rom.youtube-video-id')"
      prefix-label="stacked"
      variant="outlined"
      density="comfortable"
      clearable
      hide-details
      @update:model-value="
        (v) =>
          updateManualMetadata(
            'youtube_video_id',
            v && String(v).trim() !== '' ? String(v) : null,
          )
      "
    />
    <div class="r-additional__lockable">
      <RComboboxField
        :model-value="ageRatingsView"
        :items="AGE_RATING_ITEMS"
        :label="t('rom.age-ratings')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="
          (v) =>
            updateManualMetadata(
              'age_ratings',
              v.map((r) => r.split(' - ').join(':')),
            )
        "
      />
      <MetadataLockControl
        field="age_ratings"
        :label="t('rom.age-ratings')"
        :locked="metadataLockedFields.includes('age_ratings')"
        :disabled="metadataLockDisabled"
        @toggle="emit('toggle-metadata-lock', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.r-additional {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.r-additional__lockable {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}
</style>
