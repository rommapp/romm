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
import type { UpdateRom } from "@/services/api/rom";

const props = defineProps<{ rom: UpdateRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

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

const FIELDS: IdField[] = [
  { key: "igdb_id", label: "IGDB ID", type: "number" },
  { key: "moby_id", label: "MobyGames ID", type: "number" },
  { key: "ss_id", label: "ScreenScraper ID", type: "number" },
  { key: "ra_id", label: "RetroAchievements ID", type: "number" },
  { key: "launchbox_id", label: "LaunchBox ID", type: "number" },
  { key: "sgdb_id", label: "SteamGridDB ID", type: "number" },
  { key: "hasheous_id", label: "Hasheous ID", type: "number" },
  { key: "flashpoint_id", label: "Flashpoint ID", type: "string" },
  { key: "hltb_id", label: "HowLongToBeat ID", type: "number" },
];

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
    <RTextField
      v-for="field in FIELDS"
      :key="field.key"
      :model-value="modelFor(field)"
      :label="field.label"
      prefix-label="stacked"
      variant="outlined"
      density="comfortable"
      clearable
      hide-details
      @update:model-value="(v) => onUpdate(field, v)"
    />
  </div>
</template>

<style scoped>
.r-v2-meta-ids {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
</style>
