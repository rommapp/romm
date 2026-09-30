<script setup lang="ts">
// InstallCacheManager - every install cache on disk with its size and age,
// plus the total, with per-game and delete-all actions. Backs the "Install
// cache" block of Settings > Library Management > Stream Install.
import { RBtn, REmptyState, RIcon, RSpinner } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import installApi from "@/services/api/install";
import type { InstallCache, InstallCacheEntry } from "@/services/api/install";
import { formatBytes } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const props = defineProps<{ canEdit: boolean }>();

const { t, locale } = useI18n();
const confirm = useConfirm();
const snackbar = useSnackbar();

const cache = ref<InstallCache | null>(null);
const loading = ref(true);
const busyId = ref<number | "all" | null>(null);

const DAY_MS = 86_400_000;

async function load() {
  loading.value = true;
  try {
    const { data } = await installApi.getInstallCache();
    cache.value = data;
  } catch {
    cache.value = null;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const entries = computed(() => cache.value?.entries ?? []);

const relativeTime = computed(
  () =>
    new Intl.RelativeTimeFormat(locale.value.replace("_", "-"), {
      numeric: "auto",
    }),
);

// Age of the cache since its install last changed.
function age(entry: InstallCacheEntry): string {
  const days = Math.floor((Date.now() - Date.parse(entry.updated_at)) / DAY_MS);
  if (days >= 1) return relativeTime.value.format(-days, "day");
  const hours = Math.floor(
    (Date.now() - Date.parse(entry.updated_at)) / 3_600_000,
  );
  return relativeTime.value.format(-hours, "hour");
}

function isRunning(entry: InstallCacheEntry) {
  return entry.state === "installing" || entry.state === "streaming";
}

function errorDetail(err: unknown): string {
  const e = err as {
    response?: { data?: { detail?: string }; statusText?: string };
    message?: string;
  };
  return (
    e?.response?.data?.detail || e?.response?.statusText || e?.message || ""
  );
}

async function removeOne(entry: InstallCacheEntry) {
  const name = entry.rom_name ?? `#${entry.rom_id}`;
  const ok = await confirm({
    title: t("settings.install-cache-delete-title"),
    body: t("settings.install-cache-delete-body", {
      name,
      size: formatBytes(entry.size_bytes, 1),
    }),
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: "DELETE",
  });
  if (!ok) return;
  busyId.value = entry.session_id;
  try {
    await installApi.deleteInstallCache(entry.session_id);
    snackbar.success(t("settings.install-cache-deleted", { name }));
    await load();
  } catch (err) {
    snackbar.error(
      t("settings.install-cache-delete-error", { detail: errorDetail(err) }),
    );
  } finally {
    busyId.value = null;
  }
}

async function removeAll() {
  const ok = await confirm({
    title: t("settings.install-cache-delete-all-title"),
    body: t("settings.install-cache-delete-all-body", {
      size: formatBytes(cache.value?.total_bytes ?? 0, 1),
    }),
    confirmText: t("settings.install-cache-delete-all"),
    tone: "danger",
    requireTyped: "DELETE",
  });
  if (!ok) return;
  busyId.value = "all";
  try {
    const { data } = await installApi.deleteAllInstallCaches();
    snackbar.success(
      t("settings.install-cache-deleted-all", {
        n: data.removed,
        size: formatBytes(data.freed_bytes, 1),
      }),
    );
    if (data.skipped > 0) {
      snackbar.warning(
        t("settings.install-cache-skipped-running", { n: data.skipped }),
      );
    }
    await load();
  } catch (err) {
    snackbar.error(
      t("settings.install-cache-delete-error", { detail: errorDetail(err) }),
    );
  } finally {
    busyId.value = null;
  }
}
</script>

<template>
  <div class="r-v2-cache">
    <div class="r-v2-cache__head">
      <div class="r-v2-cache__total">
        <span class="r-v2-cache__total-label">
          {{ t("settings.install-cache-total") }}
        </span>
        <strong>{{ formatBytes(cache?.total_bytes ?? 0, 1) }}</strong>
      </div>
      <RBtn
        variant="outlined"
        size="small"
        color="error"
        prepend-icon="mdi-database-remove"
        :loading="busyId === 'all'"
        :disabled="!props.canEdit || entries.length === 0 || busyId !== null"
        @click="removeAll"
      >
        {{ t("settings.install-cache-delete-all") }}
      </RBtn>
    </div>

    <div v-if="loading" class="r-v2-cache__loading">
      <RSpinner />
    </div>
    <REmptyState
      v-else-if="entries.length === 0"
      icon="mdi-harddisk"
      :title="t('settings.install-cache-empty')"
    />
    <ul v-else class="r-v2-cache__list">
      <li
        v-for="entry in entries"
        :key="entry.session_id"
        class="r-v2-cache__row"
      >
        <div class="r-v2-cache__info">
          <span class="r-v2-cache__name">
            {{ entry.rom_name ?? `#${entry.rom_id}` }}
          </span>
          <span class="r-v2-cache__meta">
            <RIcon icon="mdi-harddisk" size="12" />
            {{ formatBytes(entry.size_bytes, 1) }}
            <span aria-hidden="true">·</span>
            {{ age(entry) }}
          </span>
        </div>
        <RBtn
          variant="text"
          size="small"
          color="error"
          icon="mdi-delete-outline"
          :aria-label="t('settings.install-cache-delete-title')"
          :loading="busyId === entry.session_id"
          :disabled="!props.canEdit || isRunning(entry) || busyId !== null"
          :title="
            isRunning(entry)
              ? t('settings.install-cache-running-hint')
              : undefined
          "
          @click="removeOne(entry)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.r-v2-cache__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.r-v2-cache__total {
  display: flex;
  flex-direction: column;
  font-size: 15px;
  color: var(--r-color-fg-primary);
}
.r-v2-cache__total-label {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-cache__loading {
  display: flex;
  justify-content: center;
  padding: 12px;
}
.r-v2-cache__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.r-v2-cache__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-cache__row:last-child {
  border-bottom: none;
}
.r-v2-cache__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.r-v2-cache__name {
  font-size: 13px;
  color: var(--r-color-fg-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-cache__meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
