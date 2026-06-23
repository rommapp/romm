<script setup lang="ts">
// AdditionalDetails (v2) — manual metadata overrides for the edit-ROM
// dialog. Companies / genres / franchises / game modes / age ratings
// are multi-tag combobox fields; first release date is a date picker;
// YouTube video ID is a plain text field.
//
// All writes go through `manual_metadata` — the backend layer where
// admins override automatic scraper output. Emitting `update:rom` with
// the merged shape keeps the parent in charge of when to actually
// commit (Save button on EditRomDialog).
import { RComboboxField, RDateField, RTextField } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { UpdateRom } from "@/services/api/rom";
import LockableField from "@/v2/components/EditRom/LockableField.vue";
import { useMetadataLocks } from "@/v2/composables/useMetadataLocks";

const props = defineProps<{ rom: UpdateRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const { t } = useI18n();

const { isLocked, toggleLock } = useMetadataLocks(
  () => props.rom,
  (rom) => emit("update:rom", rom),
);

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

// Age ratings are stored as `SYSTEM:RATING` strings — convert to the
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
  <div class="r-v2-additional">
    <LockableField
      :locked="isLocked('companies')"
      @toggle="toggleLock('companies')"
    >
      <RComboboxField
        :model-value="manual.companies ?? []"
        :label="t('rom.companies')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('companies')"
        @update:model-value="(v) => updateManualMetadata('companies', v)"
      />
    </LockableField>
    <LockableField :locked="isLocked('genres')" @toggle="toggleLock('genres')">
      <RComboboxField
        :model-value="manual.genres ?? []"
        :label="t('rom.genres')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('genres')"
        @update:model-value="(v) => updateManualMetadata('genres', v)"
      />
    </LockableField>
    <LockableField
      :locked="isLocked('franchises')"
      @toggle="toggleLock('franchises')"
    >
      <RComboboxField
        :model-value="manual.franchises ?? []"
        :label="t('rom.franchises')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('franchises')"
        @update:model-value="(v) => updateManualMetadata('franchises', v)"
      />
    </LockableField>
    <LockableField
      :locked="isLocked('first_release_date')"
      @toggle="toggleLock('first_release_date')"
    >
      <RDateField
        :model-value="manual.first_release_date ?? null"
        :label="t('rom.released-at')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('first_release_date')"
        @update:model-value="
          (d) =>
            updateManualMetadata('first_release_date', d ? d.getTime() : null)
        "
      />
    </LockableField>
    <LockableField
      :locked="isLocked('game_modes')"
      @toggle="toggleLock('game_modes')"
    >
      <RComboboxField
        :model-value="manual.game_modes ?? []"
        :items="GAME_MODE_ITEMS"
        :label="t('rom.game-modes')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('game_modes')"
        @update:model-value="(v) => updateManualMetadata('game_modes', v)"
      />
    </LockableField>
    <LockableField
      :locked="isLocked('youtube_video_id')"
      @toggle="toggleLock('youtube_video_id')"
    >
      <RTextField
        :model-value="manual.youtube_video_id ?? ''"
        :label="t('rom.youtube-video-id')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        hide-details
        :disabled="isLocked('youtube_video_id')"
        @update:model-value="
          (v) =>
            updateManualMetadata(
              'youtube_video_id',
              v && String(v).trim() !== '' ? String(v) : null,
            )
        "
      />
    </LockableField>
    <LockableField
      :locked="isLocked('age_ratings')"
      @toggle="toggleLock('age_ratings')"
    >
      <RComboboxField
        :model-value="ageRatingsView"
        :items="AGE_RATING_ITEMS"
        :label="t('rom.age-ratings')"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        :disabled="isLocked('age_ratings')"
        @update:model-value="
          (v) =>
            updateManualMetadata(
              'age_ratings',
              v.map((r) => r.split(' - ').join(':')),
            )
        "
      />
    </LockableField>
  </div>
</template>

<style scoped>
.r-v2-additional {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
</style>
