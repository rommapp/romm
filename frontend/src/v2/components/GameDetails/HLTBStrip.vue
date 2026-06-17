<script setup lang="ts">
// HLTBStrip — "How Long To Beat" stats bar. Up to four columns (main story,
// main + extras, completionist, all styles). Each column: uppercase label,
// big value, optional "N players" subcount.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RomHLTBMetadata } from "@/__generated__";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ metadata: RomHLTBMetadata | null | undefined }>();

const { t } = useI18n();

type Entry = { label: string; value: string; count: number | null };

// Backend stores HLTB durations in seconds. Convert to hours, round to
// the nearest 0.5h (mirrors v1's HowLongToBeat.vue), or to minutes when
// the game is shorter than an hour.
const intlHours = new Intl.NumberFormat("en-US", {
  maximumSignificantDigits: 3,
});

function formatHours(secs?: number | null) {
  if (!secs || secs <= 0) return null;
  const hours = secs / 3600;
  if (hours < 1) {
    const mins = Math.round(secs / 60);
    return mins > 0 ? `${mins}m` : null;
  }
  return `${intlHours.format(Math.round(hours * 2) / 2)}h`;
}

const entries = computed<Entry[]>(() => {
  const m = props.metadata;
  if (!m) return [];
  const out: Entry[] = [];
  const candidates: [string, number | undefined, number | undefined][] = [
    [t("rom.main-story"), m.main_story, m.main_story_count],
    [t("rom.main-plus-extra"), m.main_plus_extra, m.main_plus_extra_count],
    [t("rom.completionist"), m.completionist, m.completionist_count],
    [t("rom.all-styles"), m.all_styles, m.all_styles_count],
  ];
  for (const [label, value, count] of candidates) {
    const v = formatHours(value);
    if (v) out.push({ label, value: v, count: count ?? null });
  }
  return out;
});
</script>

<template>
  <div v-if="entries.length" class="r-v2-det-hltb">
    <div v-for="e in entries" :key="e.label" class="r-v2-det-hltb__item">
      <div class="r-v2-det-hltb__label">
        {{ e.label }}
      </div>
      <div class="r-v2-det-hltb__value">
        {{ e.value }}
      </div>
      <div v-if="e.count" class="r-v2-det-hltb__sub">
        {{ t("rom.players-n", { n: e.count.toLocaleString() }) }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-v2-det-hltb {
  display: flex;
  align-items: stretch;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  padding: 14px 0;
  max-width: 720px;
}

.r-v2-det-hltb__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 0 12px;
  border-right: 1px solid var(--r-color-border);
}
.r-v2-det-hltb__item:last-child {
  border-right: none;
}

.r-v2-det-hltb__label {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  text-align: center;
}
.r-v2-det-hltb__value {
  font-size: 20px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
}
.r-v2-det-hltb__sub {
  font-size: 10px;
  color: var(--r-color-fg-faint);
}
</style>
