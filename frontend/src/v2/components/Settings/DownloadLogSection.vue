<script setup lang="ts">
// DownloadLogSection, the per-download audit log. Admin-only surface:
// these rows carry usernames, client IPs and user agents, which is why
// nothing here is mirrored on the public game page.
//
// Paging is server-side (offset/limit) rather than fetch-all-then-slice,
// because the log grows without bound on a busy server.
import {
  RBtn,
  RChip,
  RIcon,
  RSelect,
  RTable,
  RTooltip,
  type RTableColumn,
} from "@v2/lib";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { DownloadLogEntry, DownloadSource } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import downloadApi from "@/services/api/download";
import { formatBytes, formatTimestamp } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const PAGE_SIZE = 25;

const { t, locale } = useI18n();
const router = useRouter();
const snackbar = useSnackbar();

const entries = ref<DownloadLogEntry[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(true);
const sourceFilter = ref<DownloadSource | null>(null);
const daysFilter = ref<number | null>(null);

const sourceOptions = computed(() => [
  { title: t("settings.downloads-source-all"), value: null },
  { title: t("settings.downloads-source-webui"), value: "webui" },
  { title: t("settings.downloads-source-client-token"), value: "client_token" },
  { title: t("settings.downloads-source-oauth"), value: "oauth" },
  { title: t("settings.downloads-source-basic-auth"), value: "basic_auth" },
  { title: t("settings.downloads-source-anonymous"), value: "anonymous" },
]);

const windowOptions = computed(() => [
  { title: t("settings.downloads-window-all"), value: null },
  { title: t("settings.downloads-window-days", { days: 1 }), value: 1 },
  { title: t("settings.downloads-window-days", { days: 7 }), value: 7 },
  { title: t("settings.downloads-window-days", { days: 30 }), value: 30 },
  { title: t("settings.downloads-window-days", { days: 90 }), value: 90 },
]);

const columns = computed<RTableColumn[]>(() => [
  {
    key: "downloaded_at",
    label: t("settings.downloads-column-when"),
    width: "170px",
    skeletonWidth: 130,
  },
  {
    key: "username",
    label: t("settings.tokens-admin-table-user"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 90,
  },
  {
    key: "rom_name",
    label: t("common.name"),
    width: "minmax(0, 2fr)",
    skeletonWidth: 170,
  },
  {
    key: "platform_name",
    label: t("common.platform"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 90,
  },
  {
    key: "source",
    label: t("settings.downloads-column-source"),
    width: "130px",
    skeletonWidth: 70,
  },
  {
    key: "size_bytes",
    label: t("common.size-on-disk"),
    width: "100px",
    align: "end",
    skeletonWidth: 60,
  },
  {
    key: "client_ip",
    label: t("settings.downloads-column-client"),
    width: "140px",
    align: "end",
    skeletonWidth: 90,
  },
]);

const rangeStart = computed(() => (total.value === 0 ? 0 : offset.value + 1));
const rangeEnd = computed(() =>
  Math.min(offset.value + entries.value.length, total.value),
);
const canPrev = computed(() => offset.value > 0);
const canNext = computed(() => offset.value + PAGE_SIZE < total.value);

const SOURCE_LABEL_KEYS: Record<string, string> = {
  webui: "settings.downloads-source-webui",
  client_token: "settings.downloads-source-client-token",
  oauth: "settings.downloads-source-oauth",
  basic_auth: "settings.downloads-source-basic-auth",
  anonymous: "settings.downloads-source-anonymous",
};

function sourceLabel(source: string): string {
  const key = SOURCE_LABEL_KEYS[source];
  return key ? t(key) : source;
}

async function fetchPage() {
  loading.value = true;
  try {
    const { data } = await downloadApi.fetchLog({
      limit: PAGE_SIZE,
      offset: offset.value,
      source: sourceFilter.value ?? undefined,
      days: daysFilter.value ?? undefined,
    });
    entries.value = data.items;
    total.value = data.total;
  } catch (err) {
    console.error(err);
    snackbar.error(t("settings.downloads-log-error"), {
      icon: "mdi-close-circle",
    });
  } finally {
    loading.value = false;
  }
}

// Any filter change invalidates the current offset, restart at page one.
watch([sourceFilter, daysFilter], () => {
  offset.value = 0;
  fetchPage();
});

function prevPage() {
  if (!canPrev.value) return;
  offset.value = Math.max(0, offset.value - PAGE_SIZE);
  fetchPage();
}

function nextPage() {
  if (!canNext.value) return;
  offset.value += PAGE_SIZE;
  fetchPage();
}

function openRom(entry: DownloadLogEntry) {
  if (entry.rom_id === null) return;
  router.push({ name: ROUTES.ROM, params: { rom: entry.rom_id } });
}

onMounted(fetchPage);
</script>

<template>
  <SettingsSection
    :title="t('settings.downloads-log')"
    icon="mdi-format-list-bulleted"
  >
    <div class="r-v2-dl-log">
      <div class="r-v2-dl-log__toolbar">
        <RSelect
          v-model="sourceFilter"
          :items="sourceOptions"
          :label="t('settings.downloads-column-source')"
          variant="outlined"
          density="compact"
          hide-details
          class="r-v2-dl-log__filter"
        />
        <RSelect
          v-model="daysFilter"
          :items="windowOptions"
          :label="t('settings.downloads-filter-period')"
          variant="outlined"
          density="compact"
          hide-details
          class="r-v2-dl-log__filter"
        />
        <RTooltip>
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              variant="text"
              size="small"
              icon="mdi-refresh"
              :aria-label="t('settings.downloads-refresh')"
              class="r-v2-dl-log__refresh"
              @click="fetchPage"
            />
          </template>
          <span>{{ t("settings.downloads-refresh") }}</span>
        </RTooltip>
      </div>

      <RTable
        :columns="columns"
        :items="entries"
        :item-key="(r) => (r as DownloadLogEntry).id"
        :loading="loading"
        :loading-rows="8"
        clickable-rows
        min-width="980px"
        empty-icon="mdi-download-off-outline"
        :empty-message="t('settings.downloads-log-empty')"
        @row:click="(row) => openRom(row as DownloadLogEntry)"
      >
        <template #cell.downloaded_at="{ row }">
          <span class="r-v2-dl-log__meta">
            {{
              formatTimestamp((row as DownloadLogEntry).downloaded_at, locale)
            }}
          </span>
        </template>
        <template #cell.username="{ row }">
          <span class="r-v2-dl-log__user">
            {{ (row as DownloadLogEntry).username }}
          </span>
        </template>
        <template #cell.rom_name="{ row }">
          <span class="r-v2-dl-log__name">
            {{ (row as DownloadLogEntry).rom_name }}
            <RIcon
              v-if="(row as DownloadLogEntry).kind === 'file'"
              icon="mdi-file-outline"
              size="13"
              class="r-v2-dl-log__kind"
              :title="t('settings.downloads-kind-file')"
            />
          </span>
        </template>
        <template #cell.platform_name="{ row }">
          <span class="r-v2-dl-log__meta">
            {{ (row as DownloadLogEntry).platform_name }}
          </span>
        </template>
        <template #cell.source="{ row }">
          <RChip size="x-small" variant="translucent">
            {{ sourceLabel((row as DownloadLogEntry).source) }}
          </RChip>
        </template>
        <template #cell.size_bytes="{ row }">
          <span class="r-v2-dl-log__meta">
            {{ formatBytes((row as DownloadLogEntry).size_bytes, 1) }}
          </span>
        </template>
        <template #cell.client_ip="{ row }">
          <RTooltip v-if="(row as DownloadLogEntry).user_agent">
            <template #activator="{ props: tipProps }">
              <span v-bind="tipProps" class="r-v2-dl-log__meta">
                {{ (row as DownloadLogEntry).client_ip ?? "—" }}
              </span>
            </template>
            <span>{{ (row as DownloadLogEntry).user_agent }}</span>
          </RTooltip>
          <span v-else class="r-v2-dl-log__meta">
            {{ (row as DownloadLogEntry).client_ip ?? "—" }}
          </span>
        </template>
      </RTable>

      <div v-if="total > 0" class="r-v2-dl-log__pager">
        <span class="r-v2-dl-log__range">
          {{
            t("settings.downloads-log-range", {
              start: rangeStart,
              end: rangeEnd,
              total,
            })
          }}
        </span>
        <RBtn
          variant="text"
          size="small"
          icon="mdi-chevron-left"
          :disabled="!canPrev"
          :aria-label="t('common.previous-page')"
          @click="prevPage"
        />
        <RBtn
          variant="text"
          size="small"
          icon="mdi-chevron-right"
          :disabled="!canNext"
          :aria-label="t('common.next-page')"
          @click="nextPage"
        />
      </div>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-dl-log {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.r-v2-dl-log__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.r-v2-dl-log__filter {
  flex: 0 1 200px;
  min-width: 0;
}

.r-v2-dl-log__refresh {
  margin-left: auto;
}

.r-v2-dl-log__user {
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-dl-log__name {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-dl-log__kind {
  flex-shrink: 0;
  color: var(--r-color-fg-faint);
}

.r-v2-dl-log__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.r-v2-dl-log__pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.r-v2-dl-log__range {
  margin-right: auto;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}
</style>
