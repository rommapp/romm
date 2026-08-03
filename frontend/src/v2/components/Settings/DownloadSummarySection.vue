<script setup lang="ts">
// DownloadSummarySection. Headline counters for the download stats view.
// Mirrors SummaryStatsSection's card grid so the two stats pages read as
// one family. The reclaimable-space card is tinted as a warning because
// it is the number that prompts a deletion.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DownloadStatsSummary } from "@/__generated__";
import { formatBytes } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  summary: DownloadStatsSummary;
  windowDays: number;
}
const props = defineProps<Props>();

const { t } = useI18n();

interface StatCard {
  key: string;
  icon: string;
  value: string;
  label: string;
  hint?: string;
  tone?: "warning";
}

const coveragePercent = computed(() => {
  if (!props.summary.roms_total) return 0;
  return (
    (props.summary.unique_roms_downloaded / props.summary.roms_total) * 100
  );
});

const cards = computed<StatCard[]>(() => [
  {
    key: "total",
    icon: "mdi-download",
    value: props.summary.total_downloads.toLocaleString(),
    label: t("settings.downloads-total"),
    hint: formatBytes(props.summary.total_bytes, 1),
  },
  {
    key: "window",
    icon: "mdi-calendar-range",
    value: props.summary.downloads_in_window.toLocaleString(),
    label: t("settings.downloads-in-window", { days: props.windowDays }),
    hint: formatBytes(props.summary.bytes_in_window, 1),
  },
  {
    key: "roms",
    icon: "mdi-disc",
    value: props.summary.unique_roms_downloaded.toLocaleString(),
    label: t("settings.downloads-unique-games"),
    hint: t("settings.downloads-of-library", {
      total: props.summary.roms_total.toLocaleString(),
      percent: coveragePercent.value.toFixed(1),
    }),
  },
  {
    key: "users",
    icon: "mdi-account-multiple-outline",
    value: props.summary.unique_users.toLocaleString(),
    label: t("settings.downloads-unique-users"),
  },
  {
    key: "never",
    icon: "mdi-download-off-outline",
    value: props.summary.never_downloaded_count.toLocaleString(),
    label: t("settings.downloads-never-downloaded"),
    tone: "warning",
  },
  {
    key: "reclaimable",
    icon: "mdi-harddisk-remove",
    value: formatBytes(props.summary.never_downloaded_bytes, 1),
    label: t("settings.downloads-reclaimable"),
    tone: "warning",
  },
]);
</script>

<template>
  <SettingsSection
    :title="t('settings.downloads-summary')"
    icon="mdi-chart-bar"
  >
    <div class="r-v2-dl-summary">
      <div
        v-for="card in cards"
        :key="card.key"
        class="r-v2-dl-summary__card"
        :class="{ 'r-v2-dl-summary__card--warning': card.tone === 'warning' }"
      >
        <RIcon :icon="card.icon" size="22" />
        <div class="r-v2-dl-summary__value">{{ card.value }}</div>
        <div class="r-v2-dl-summary__label">{{ card.label }}</div>
        <div v-if="card.hint" class="r-v2-dl-summary__hint">
          {{ card.hint }}
        </div>
      </div>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-dl-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
html[data-bp~="sm-and-down"] .r-v2-dl-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
html[data-bp~="xs"] .r-v2-dl-summary {
  grid-template-columns: minmax(0, 1fr);
}

.r-v2-dl-summary__card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 16px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  color: var(--r-color-fg-muted);
}

.r-v2-dl-summary__card--warning {
  border-color: color-mix(in srgb, var(--r-color-warning) 35%, transparent);
  color: var(--r-color-warning);
}

.r-v2-dl-summary__value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: var(--r-color-fg);
  font-variant-numeric: tabular-nums;
}

.r-v2-dl-summary__card--warning .r-v2-dl-summary__value {
  color: var(--r-color-warning);
}

.r-v2-dl-summary__label {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.r-v2-dl-summary__hint {
  font-size: 11px;
  color: var(--r-color-fg-faint);
  font-variant-numeric: tabular-nums;
}
</style>
