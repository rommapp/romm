<script setup lang="ts">
// MetadataTab — four sections, top to bottom:
//   1. File info — name + size only.
//   2. Hashes — CRC, MD5, SHA1, all mono. RTag with eyebrow label.
//   3. Verification — RTag per database; tone="success" for match,
//      neutral for miss. Same source of truth (Hasheous match flags) as
//      the "Verified" badge in the header, via `VERIFICATION_DATABASES`.
//   4. Metadata sources — ProviderGrid (linked + unlinked).
import { RTag } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import { PROVIDERS } from "@/v2/components/GameDetails/providers";
import ProviderGrid from "@/v2/components/GameDetails/ProviderGrid.vue";
import HashChip from "@/v2/components/shared/HashChip.vue";
import {
  matchesDatabase,
  VERIFICATION_DATABASES,
} from "@/v2/utils/romVerification";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();

type Row = { label: string; value: string };

const fileRows = computed<Row[]>(() => {
  const r = props.rom;
  const size = r.fs_size_bytes != null ? formatBytes(r.fs_size_bytes) : "—";
  return [
    { label: t("rom.filename"), value: r.fs_name },
    { label: t("common.size"), value: size },
  ];
});

// Hash rows accept `value: string | null` because HashChip's click-to-
// copy contract requires the full untruncated source; missing hashes
// render as a dash via the fallback chip below.
const hashRows = computed<{ label: string; value: string | null }[]>(() => {
  const r = props.rom;
  // CHD SHA-1 lives on the file, not the ROM — surface it at ROM level
  // only when the ROM is a single CHD file. Skipped (not dashed) when
  // not applicable since most ROMs aren't CHDs.
  const chdSha1 = r.has_simple_single_file
    ? (r.files[0]?.chd_sha1_hash ?? null)
    : null;
  const rows: { label: string; value: string | null }[] = [
    { label: "CRC", value: r.crc_hash },
    { label: "MD5", value: r.md5_hash },
    { label: "SHA1", value: r.sha1_hash },
    { label: "RA", value: r.ra_hash },
  ];
  if (chdSha1) rows.splice(3, 0, { label: "CHD SHA-1", value: chdSha1 });
  return rows;
});

type Verification = { label: string; match: boolean };

// Per-database match badges, driven by the shared VERIFICATION_DATABASES
// so this list stays in lockstep with the header badge and the backend
// filter. A match means the ROM's hash was found in that database (via
// Hasheous), which is what "verified" communicates.
const verifications = computed<Verification[]>(() =>
  VERIFICATION_DATABASES.map((db) => ({
    label: db.label,
    match: matchesDatabase(props.rom, db.keys),
  })),
);

type RatingChip = {
  key: "igdb_id" | "ss_id" | "moby_id" | "launchbox_id" | "hltb_id";
  name: string;
  logo: string;
  value: string;
};

function formatRating(value: number, options?: { percent?: boolean }): string | null {
  if (!Number.isFinite(value)) return null;
  const rounded = value >= 10 ? value.toFixed(0) : value.toFixed(1);
  const formatted = rounded.replace(/\.0$/, "");
  return options?.percent ? `${formatted}%` : formatted;
}

function normalizeToTen(value: number): number {
  if (!Number.isFinite(value)) return Number.NaN;
  return value > 10 ? value / 10 : value;
}

function providerByKey(key: RatingChip["key"]) {
  return PROVIDERS.find((p) => p.key === key) ?? null;
}

const ratingChips = computed<RatingChip[]>(() => {
  const rom = props.rom;

  const values: Array<{ key: RatingChip["key"]; value: string | null }> = [
    {
      key: "igdb_id",
      value: formatRating(
        normalizeToTen(parseFloat(rom.igdb_metadata?.total_rating ?? "")),
      ),
    },
    {
      key: "ss_id",
      value: formatRating(parseFloat(rom.ss_metadata?.ss_score ?? "") * 10, {
        percent: true,
      }),
    },
    {
      key: "moby_id",
      value: formatRating(parseFloat(rom.moby_metadata?.moby_score ?? "") * 10, {
        percent: true,
      }),
    },
    {
      key: "launchbox_id",
      value: formatRating(
        (rom.launchbox_metadata?.community_rating ?? Number.NaN) * 20,
        { percent: true },
      ),
    },
    {
      key: "hltb_id",
      value: formatRating(rom.hltb_metadata?.review_score ?? Number.NaN, {
        percent: true,
      }),
    },
  ];

  const out: RatingChip[] = [];

  for (const entry of values) {
    if (!entry.value) continue;
    const provider = providerByKey(entry.key);
    if (!provider || !provider.logo) continue;

    out.push({
      key: entry.key,
      name: provider.name,
      logo: provider.logo,
      value: entry.value,
    });
  }

  return out;
});
</script>

<template>
  <div class="metadata-tab">
    <!-- 1. File info -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">{{ t("rom.file-info") }}</h3>
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
      <h3 class="metadata-tab__heading">{{ t("rom.hashes-label") }}</h3>
      <div class="metadata-tab__inline">
        <template v-for="row in hashRows" :key="row.label">
          <HashChip v-if="row.value" :label="row.label" :value="row.value" />
          <RTag v-else :label="row.label" text="—" mono />
        </template>
      </div>
    </section>

    <!-- 3. Verification -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">{{ t("rom.verification") }}</h3>
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

    <!-- 4. Ratings -->
    <section v-if="ratingChips.length" class="metadata-tab__section">
      <h3 class="metadata-tab__heading">{{ t("rom.ratings-label") }}</h3>
      <div class="metadata-tab__ratings">
        <span
          v-for="chip in ratingChips"
          :key="chip.key"
          class="metadata-tab__rating-inline"
          :aria-label="`${chip.name} rating ${chip.value}`"
        >
          <img
            class="metadata-tab__rating-logo"
            :src="chip.logo"
            :alt="`${chip.name} logo`"
          />
          <span class="metadata-tab__rating-value">{{ chip.value }}</span>
        </span>
      </div>
    </section>

    <!-- 5. Provider links -->
    <section class="metadata-tab__section">
      <h3 class="metadata-tab__heading">
        {{ t("rom.metadata-sources-label") }}
      </h3>
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

/* Ratings — logo + value pairs in a flex row. */
.metadata-tab__ratings {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metadata-tab__rating-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--r-radius-sm);
  background-color: var(--r-color-surface-secondary);
  color: var(--r-color-fg);
}

.metadata-tab__rating-logo {
  inline-size: 16px;
  block-size: 16px;
  object-fit: contain;
  flex-shrink: 0;
}

.metadata-tab__rating-value {
  font-variant-numeric: tabular-nums;
  font-weight: var(--r-font-weight-semibold);
}
</style>
