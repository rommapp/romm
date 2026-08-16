<script setup lang="ts">
// DownloadStatsSection, the "Downloads" tab of the Administration page.
// Owns the overview fetch and the trailing-window selector, then hands
// slices down to the presentational sections.
//
// The per-download log fetches its own pages (it has its own filters and
// paging), so it isn't part of the overview payload.
import { RIcon, RSelect, RSpinner } from "@v2/lib";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { DownloadStatsOverview } from "@/__generated__";
import downloadApi from "@/services/api/download";
import DownloadLogSection from "@/v2/components/Settings/DownloadLogSection.vue";
import DownloadSummarySection from "@/v2/components/Settings/DownloadSummarySection.vue";
import DownloadTimelineSection from "@/v2/components/Settings/DownloadTimelineSection.vue";
import TopDownloadsSection from "@/v2/components/Settings/TopDownloadsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const TOP_LIMIT = 10;

const { t } = useI18n();
const snackbar = useSnackbar();

const overview = ref<DownloadStatsOverview | null>(null);
const loading = ref(true);
const windowDays = ref(30);

const windowOptions = computed(() => [
  { title: t("settings.downloads-window-days", { days: 7 }), value: 7 },
  { title: t("settings.downloads-window-days", { days: 30 }), value: 30 },
  { title: t("settings.downloads-window-days", { days: 90 }), value: 90 },
  { title: t("settings.downloads-window-days", { days: 365 }), value: 365 },
]);

async function fetchOverview() {
  loading.value = true;
  try {
    const { data } = await downloadApi.fetchOverview({
      days: windowDays.value,
      topLimit: TOP_LIMIT,
    });
    overview.value = data;
  } catch (err) {
    console.error(err);
    snackbar.error(t("settings.downloads-stats-error"), {
      icon: "mdi-close-circle",
    });
  } finally {
    loading.value = false;
  }
}

watch(windowDays, fetchOverview);
onMounted(fetchOverview);
</script>

<template>
  <div class="r-v2-dl-stats">
    <div class="r-v2-dl-stats__toolbar">
      <div class="r-v2-dl-stats__hint">
        <RIcon icon="mdi-information-outline" size="15" />
        <span>{{ t("settings.downloads-intro") }}</span>
      </div>
      <RSelect
        v-model="windowDays"
        :items="windowOptions"
        :label="t('settings.downloads-filter-period')"
        variant="outlined"
        density="compact"
        hide-details
        class="r-v2-dl-stats__window"
      />
    </div>

    <div v-if="loading && !overview" class="r-v2-dl-stats__loading">
      <RSpinner size="28" />
    </div>

    <template v-else-if="overview">
      <DownloadSummarySection
        :summary="overview.summary"
        :window-days="windowDays"
      />
      <DownloadTimelineSection :timeline="overview.timeline" />
      <TopDownloadsSection :roms="overview.top_roms" :loading="loading" />
    </template>

    <DownloadLogSection />
  </div>
</template>

<style scoped>
.r-v2-dl-stats {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.r-v2-dl-stats__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.r-v2-dl-stats__hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  min-width: 0;
}

.r-v2-dl-stats__window {
  margin-left: auto;
  flex: 0 1 200px;
  min-width: 0;
}

.r-v2-dl-stats__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}
</style>
