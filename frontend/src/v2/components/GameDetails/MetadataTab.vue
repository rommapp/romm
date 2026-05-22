<script setup lang="ts">
// MetadataTab — four sections, top to bottom:
//   1. File info — name + size only.
//   2. Hashes — CRC, MD5, SHA1, all mono. RTag with eyebrow label.
//   3. Verification — RTag per database; tone="success" for match,
//      neutral for miss. Independent from the "Verified" pill in the
//      title header which only checks `crc_hash`. RA match comes from
//      `rom.ra_id`.
//   4. Metadata sources — ProviderGrid (linked + unlinked).
import { RTag } from "@v2/lib";
import { computed } from "vue";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import ProviderGrid from "@/v2/components/GameDetails/ProviderGrid.vue";
import HashChip from "@/v2/components/shared/HashChip.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRom }>();

type Row = { label: string; value: string };

const fileRows = computed<Row[]>(() => {
  const r = props.rom;
  const size = r.fs_size_bytes != null ? formatBytes(r.fs_size_bytes) : "—";
  return [
    { label: "File name", value: r.fs_name },
    { label: "Size", value: size },
  ];
});

// Hash rows accept `value: string | null` because HashChip's click-to-
// copy contract requires the full untruncated source; missing hashes
// render as a dash via the fallback chip below.
const hashRows = computed<{ label: string; value: string | null }[]>(() => {
  const r = props.rom;
  return [
    { label: "CRC", value: r.crc_hash },
    { label: "MD5", value: r.md5_hash },
    { label: "SHA1", value: r.sha1_hash },
  ];
});

type Verification = { label: string; match: boolean };

// Per-database match badges. Hasheous covers TOSEC / No-Intro / Redump
// / FBNeo / MAME (either Arcade or MESS counts). RA is independent —
// the rom is "verified as RA" when it has an `ra_id` linked.
const verifications = computed<Verification[]>(() => {
  const r = props.rom;
  const h = r.hasheous_metadata ?? null;
  return [
    { label: "TOSEC", match: Boolean(h?.tosec_match) },
    { label: "No-Intro", match: Boolean(h?.nointro_match) },
    { label: "Redump", match: Boolean(h?.redump_match) },
    { label: "FBNeo", match: Boolean(h?.fbneo_match) },
    {
      label: "MAME",
      match: Boolean(h?.mame_arcade_match || h?.mame_mess_match),
    },
    { label: "RA", match: Boolean(r.ra_id) },
  ];
});
</script>

<template>
  <div class="metadata-tab">
    <!-- 1. File info -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">File info</h3>
      <div class="metadata-tab__rows">
        <div v-for="row in fileRows" :key="row.label" class="metadata-tab__row">
          <div class="metadata-tab__label">{{ row.label }}</div>
          <div class="metadata-tab__value">{{ row.value }}</div>
        </div>
      </div>
    </section>

    <!-- 2. Hashes — click-to-copy via HashChip; absent hashes still
         render a "—" pill so the row layout stays predictable. -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">Hashes</h3>
      <div class="metadata-tab__inline">
        <template v-for="row in hashRows" :key="row.label">
          <HashChip v-if="row.value" :label="row.label" :value="row.value" />
          <RTag v-else :label="row.label" text="—" mono />
        </template>
      </div>
    </section>

    <!-- 3. Verification -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">Verification</h3>
      <div class="metadata-tab__inline">
        <RTag
          v-for="v in verifications"
          :key="v.label"
          :icon="v.match ? 'mdi-check-circle' : 'mdi-close-circle-outline'"
          :text="v.label"
          :tone="v.match ? 'success' : 'neutral'"
        />
      </div>
    </section>

    <!-- 4. Provider links -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">Metadata sources</h3>
      <ProviderGrid :rom="rom" />
    </section>
  </div>
</template>

<style scoped>
.metadata-tab {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.metadata-tab__section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metadata-tab__heading {
  margin: 0;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

/* File info — two-column rows on wide screens, stacked on narrow. */
.metadata-tab__rows {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px 24px;
}
.metadata-tab__row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.metadata-tab__label {
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}
.metadata-tab__value {
  font-size: 13px;
  color: var(--r-color-fg-secondary);
  word-break: break-all;
}

/* Hashes & Verification — inline row, wraps when narrow. */
.metadata-tab__inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
</style>
