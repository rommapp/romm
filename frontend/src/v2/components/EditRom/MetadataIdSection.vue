<script setup lang="ts">
// MetadataIdSection (v2) — provider ID inputs for the edit-ROM dialog.
// Each field maps a single metadata provider's ID (IGDB / MobyGames /
// ScreenScraper / RetroAchievements / LaunchBox / SteamGridDB /
// Hasheous / Flashpoint / HowLongToBeat) so admins can manually fix
// up mismatched scrapes.
//
// Feature composite — knows UpdateRom; lives under
// `components/EditRom/` next to its siblings.
import { RTextField } from "@v2/lib";
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

// `field` is keyof UpdateRom; the parsed value is `number | string |
// null` — most providers use numeric ids, Flashpoint stores a string.
function updateField(field: keyof UpdateRom, value: string | number | null) {
  emit("update:rom", { ...props.rom, [field]: value });
}

function parseIdValue(raw: string | number | null): number | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (s === "") return null;
  const n = parseInt(s, 10);
  return Number.isNaN(n) ? null : n;
}

// Field config — keeps the markup tight and lets us tweak the layout
// without re-hand-writing nine identical RTextField blocks.
interface IdField {
  key: keyof UpdateRom;
  label: string;
  type: "number" | "string";
}

const FIELDS = computed<IdField[]>(() => [
  { key: "igdb_id", label: t("rom.provider-igdb-id"), type: "number" },
  { key: "moby_id", label: t("rom.provider-mobygames-id"), type: "number" },
  { key: "ss_id", label: t("rom.provider-screenscraper-id"), type: "number" },
  {
    key: "ra_id",
    label: t("rom.provider-retroachievements-id"),
    type: "number",
  },
  {
    key: "launchbox_id",
    label: t("rom.provider-launchbox-id"),
    type: "number",
  },
  { key: "sgdb_id", label: t("rom.provider-steamgriddb-id"), type: "number" },
  { key: "hasheous_id", label: t("rom.provider-hasheous-id"), type: "number" },
  {
    key: "flashpoint_id",
    label: t("rom.provider-flashpoint-id"),
    type: "string",
  },
  { key: "hltb_id", label: t("rom.provider-howlongtobeat-id"), type: "number" },
]);

function modelFor(field: IdField): string {
  const v = props.rom[field.key];
  return v == null ? "" : String(v);
}

function onUpdate(field: IdField, raw: string | number | null) {
  if (field.type === "number") {
    updateField(field.key, parseIdValue(raw));
  } else {
    const s = raw == null ? null : String(raw);
    updateField(field.key, s && s.trim() !== "" ? s : null);
  }
}
</script>

<template>
  <div class="r-v2-meta-ids">
    <LockableField
      v-for="field in FIELDS"
      :key="field.key"
      :locked="isLocked(field.key)"
      @toggle="toggleLock(field.key)"
    >
      <RTextField
        :model-value="modelFor(field)"
        :label="field.label"
        prefix-label="stacked"
        variant="outlined"
        density="comfortable"
        clearable
        hide-details
        :disabled="isLocked(field.key)"
        @update:model-value="(v) => onUpdate(field, v)"
      />
    </LockableField>
  </div>
</template>

<style scoped>
.r-v2-meta-ids {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
</style>
