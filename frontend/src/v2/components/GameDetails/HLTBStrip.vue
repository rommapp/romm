<script setup lang="ts">
// HLTBStrip: "How long to beat" stats bar, one column per play style.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RomHLTBMetadata } from "@/__generated__";
import { toBrowserLocale } from "@/utils";
import { formatPlaytime } from "@/v2/utils/time";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ metadata: RomHLTBMetadata | null | undefined }>();

const { t, locale } = useI18n();

type Entry = { label: string; value: string; count: number | null };

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
    const v = formatPlaytime(value, toBrowserLocale(locale.value));
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
/* Shared rows keep a wrapped label from pushing its value out of line. */
.r-v2-det-hltb {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  grid-template-rows: auto auto auto;
  row-gap: 4px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  padding: 14px 0;
  max-width: 720px;
}

.r-v2-det-hltb__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: subgrid;
  grid-row: span 3;
  padding: 0 12px;
  border-right: 1px solid var(--r-color-border);
  text-align: center;
}
.r-v2-det-hltb__item:last-child {
  border-right: none;
}

/* Chrome and Edge below 117 ignore subgrid, so stack each column on its own
   there; equal columns survive, the shared rows do not. */
@supports not (grid-template-rows: subgrid) {
  .r-v2-det-hltb {
    display: flex;
  }
  .r-v2-det-hltb__item {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    gap: 4px;
  }
}

.r-v2-det-hltb__label {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  /* Break an over-long label instead of spilling over the divider. */
  overflow-wrap: break-word;
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
