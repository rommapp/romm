<script setup lang="ts">
// GameHeader — right-column header for the details view.
// Four rows, top to bottom:
//   1. Title (+ previous / next game arrows on the right)
//   2. Meta (year · platform-icon + platform · verified RTag)
//   3. Tags (regions + languages + custom tags) — RTag primitive
//   4. GameActions (Play · Download · Favorite · Share · More)
//
// Metadata-provider links live in the Metadata tab, not the header.
// Genre/franchise belong in the Overview tab info grid.
import { RIcon, RPlatformIcon, RTag, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import GameActions from "@/v2/components/GameActions/GameActions.vue";
import MainSiblingToggle from "@/v2/components/GameDetails/MainSiblingToggle.vue";
import PrevNextNav from "@/v2/components/GameDetails/PrevNextNav.vue";
import { PROVIDERS } from "@/v2/components/GameDetails/providers";
import VersionSwitcher from "@/v2/components/GameDetails/VersionSwitcher.vue";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = defineProps<{
  rom: DetailedRom;
  title: string;
  platformLabel: string;
  releaseDate: string | null;
  verified: boolean;
  regions: string[];
  languages: string[];
  tags: string[];
}>();

const actions = useGameActions(() => props.rom);

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

const visibleRegions = computed(() =>
  props.regions.filter((r) => r.trim().toLowerCase() !== "world"),
);

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
  <div class="r-v2-det-header">
    <div class="r-v2-det-header__title-row">
      <h1 class="r-v2-det-header__title">
        {{ title }}
      </h1>
      <PrevNextNav :rom-id="rom.id" />
    </div>

    <div class="r-v2-det-header__meta">
      <router-link
        v-if="actions.platformPath.value"
        :to="actions.platformPath.value"
        class="r-v2-det-header__platform"
        :aria-label="t('platform.browse-platform', { platform: platformLabel })"
      >
        <RPlatformIcon
          :slug="rom.platform_slug"
          :fs-slug="rom.platform_fs_slug"
          :alt="platformLabel"
          :size="16"
        />
        {{ platformLabel }}
      </router-link>
      <span v-if="releaseDate" class="r-v2-det-header__sep"> · </span>
      <span v-if="releaseDate">{{ releaseDate }}</span>
      <span v-if="verified" class="r-v2-det-header__sep"> · </span>
      <!-- Icon-only verified indicator. The check decagram is a strong
           enough signal on its own; the "Verified" word was just noise
           in a row that's already mostly text. The tooltip spells out
           what "verified" means (a database hash match) so the badge
           isn't cryptic; the short label is the accessible name. -->
      <span
        v-if="verified"
        class="r-v2-det-header__verified"
        :aria-label="t('rom.verified-rom')"
        tabindex="0"
      >
        <RIcon icon="mdi-check-decagram" :size="18" color="success" />
        <RTooltip
          :text="t('rom.verified-rom-hint')"
          location="top"
          activator="parent"
        />
      </span>

      <span
        v-if="ratingChips.length || visibleRegions.length || languages.length || tags.length"
        class="r-v2-det-header__sep"
      >
        ·
      </span>

      <span v-if="ratingChips.length" class="r-v2-det-header__ratings">
        <span
          v-for="chip in ratingChips"
          :key="chip.key"
          class="r-v2-det-header__rating-inline"
          :aria-label="`${chip.name} rating ${chip.value}`"
        >
          <img
            class="r-v2-det-header__rating-logo"
            :src="chip.logo"
            :alt="`${chip.name} logo`"
          />
          <span class="r-v2-det-header__rating-value">{{ chip.value }}</span>
        </span>
      </span>

      <span
        v-if="visibleRegions.length || languages.length || tags.length"
        class="r-v2-det-header__tags"
      >
        <RTag
          v-for="r in visibleRegions"
          :key="`r-${r}`"
          :text="r"
          tone="info"
          size="small"
        />
        <RTag
          v-for="l in languages"
          :key="`l-${l}`"
          :text="l"
          tone="brand"
          size="small"
        />
        <RTag v-for="t in tags" :key="`t-${t}`" :text="t" size="small" />
      </span>
    </div>

    <div v-if="rom.sibling_roms.length > 0" class="r-v2-det-header__versions">
      <VersionSwitcher :rom="rom" />
      <MainSiblingToggle :rom="rom" />
    </div>

    <GameActions :rom="rom" />
  </div>
</template>

<style scoped>
.r-v2-det-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 24px;
}

.r-v2-det-header__title-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.r-v2-det-header__title {
  flex: 1;
  min-width: 0;
  font-size: var(--r-font-size-4xl);
  font-weight: var(--r-font-weight-extrabold);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 2px 0;
  color: var(--r-color-fg-heading);
  text-shadow: 0 2px 20px var(--r-color-title-shadow);
}

.r-v2-det-header__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13.5px;
  color: var(--r-color-fg-secondary);
}
.r-v2-det-header__sep {
  opacity: 0.3;
}
.r-v2-det-header__platform {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  border-radius: var(--r-radius-sm);
  transition: color 0.12s ease;
}
.r-v2-det-header__platform:hover {
  color: var(--r-color-fg);
}

.r-v2-det-header__verified {
  position: relative;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.r-v2-det-header__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.r-v2-det-header__ratings {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.r-v2-det-header__rating-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: inherit;
}

.r-v2-det-header__rating-logo {
  inline-size: 15px;
  block-size: 15px;
  object-fit: contain;
}

.r-v2-det-header__rating-value {
  font-variant-numeric: tabular-nums;
  color: inherit;
  font-weight: inherit;
  font-size: inherit;
}

.r-v2-det-header__versions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

html[data-bp~="xs"] .r-v2-det-header__title {
  font-size: 20px;
}

/* Mobile: the cover sits centred above this header, so centre the title and
   its meta / tag rows to match instead of the desktop left-align. */
html[data-bp~="sm-and-down"] .r-v2-det-header {
  align-items: center;
  text-align: center;
  padding-top: 4px;
}
/* Stack the arrows above the centred title: beside a wrapping title they'd
   hang off the last line. */
html[data-bp~="sm-and-down"] .r-v2-det-header__title-row {
  flex-direction: column-reverse;
  align-items: center;
  align-self: stretch;
  gap: 10px;
}
html[data-bp~="sm-and-down"] .r-v2-det-header__meta,
html[data-bp~="sm-and-down"] .r-v2-det-header__tags,
html[data-bp~="sm-and-down"] .r-v2-det-header__versions {
  justify-content: center;
}
</style>
