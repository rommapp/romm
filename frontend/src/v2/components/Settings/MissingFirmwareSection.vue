<script setup lang="ts">
// MissingFirmwareSection — Settings tab listing every firmware (BIOS) file
// flagged as gone from disk, across the whole library, with a bulk cleanup.
// Before this, a stale entry could only be found by opening each platform's
// Firmware tab one at a time (issue #4075).
//
// Structured after MissingGamesSection: a platform multi-select on the left,
// a count chip plus a kebab holding cleanup-all on the right, and a bordered
// list below. It differs in how it loads: firmware sets are small (dozens per
// library, not tens of thousands), so the whole missing set is fetched once
// and the platform filter narrows it in memory rather than refetching.
import {
  RBtn,
  REmptyState,
  RIcon,
  RMenu,
  RMenuItem,
  RSelect,
  RTag,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { FirmwareSchema } from "@/__generated__";
import firmwareApi from "@/services/api/firmware";
import taskApi from "@/services/api/task";
import storePlatforms from "@/stores/platforms";
import { formatBytes } from "@/utils";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

interface PlatformItem {
  id: number;
  slug: string;
  name: string;
}

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const platformsStore = storePlatforms();
const snackbar = useSnackbar();
const confirm = useConfirm();

const { allPlatforms } = storeToRefs(platformsStore);

const missingFirmware = ref<FirmwareSchema[]>([]);
const loading = ref(true);
const cleaningUp = ref(false);
const selectedPlatformIds = ref<number[]>([]);
const platformSearch = ref("");

// Only platforms that actually have something to clean up: the rest would
// filter the list down to nothing.
const platformItems = computed<PlatformItem[]>(() => {
  const affected = new Set(missingFirmware.value.map((f) => f.platform_id));
  return allPlatforms.value
    .filter((p) => affected.has(p.id))
    .map((p) => ({ id: p.id, slug: p.slug, name: p.display_name }))
    .sort((a, b) => a.name.localeCompare(b.name));
});

const platformById = computed(
  () => new Map(platformItems.value.map((p) => [p.id, p])),
);

const rows = computed(() => {
  const picked = new Set(selectedPlatformIds.value);
  return missingFirmware.value
    .filter((f) => picked.size === 0 || picked.has(f.platform_id))
    .map((f) => ({
      firmware: f,
      platform: platformById.value.get(f.platform_id),
    }));
});

const showEmpty = computed(() => !loading.value && rows.value.length === 0);

const selectedPlatformsLabel = computed(() =>
  selectedPlatformIds.value
    .map((id) => platformById.value.get(id)?.name)
    .filter(Boolean)
    .join(", "),
);

async function fetchMissingFirmware() {
  loading.value = true;
  try {
    const { data } = await firmwareApi.getFirmware({ missing: true });
    missingFirmware.value = data;
    // A cleanup can leave a selected platform with nothing left to show.
    const stillAffected = new Set(data.map((f) => f.platform_id));
    selectedPlatformIds.value = selectedPlatformIds.value.filter((id) =>
      stillAffected.has(id),
    );
  } catch (err) {
    snackbar.error(
      t("settings.couldnt-fetch-missing-firmware", { error: String(err) }),
    );
  } finally {
    loading.value = false;
  }
}

async function cleanupAll() {
  const platformLabel = selectedPlatformsLabel.value
    ? ` ${t("common.for")} ${selectedPlatformsLabel.value}`
    : "";
  // No typed gate here (unlike the ROM cleanup): the files are already gone
  // from disk, so this only drops rows that point at nothing.
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.cleanup-firmware-confirm", { platform: platformLabel }),
    confirmText: t("settings.cleanup-all"),
    tone: "danger",
  });
  if (!ok) return;
  cleaningUp.value = true;
  try {
    // The task API takes a single `platform_id`; forward it only when the
    // filter resolves to exactly one platform, so the cleanup matches what
    // the list is showing.
    const body =
      selectedPlatformIds.value.length === 1
        ? { platform_id: selectedPlatformIds.value[0] }
        : {};
    await taskApi.runTask("cleanup_missing_firmware", body);
    snackbar.success(t("settings.cleanup-firmware-queued"));
    setTimeout(() => {
      void fetchMissingFirmware();
    }, 1500);
  } catch (err) {
    snackbar.error(t("settings.couldnt-queue-cleanup", { error: String(err) }));
  } finally {
    cleaningUp.value = false;
  }
}

onMounted(() => {
  void fetchMissingFirmware();
});
</script>

<template>
  <div class="r-v2-missing-fw">
    <div class="r-v2-missing-fw__toolbar">
      <RSelect
        v-model="selectedPlatformIds"
        v-model:search="platformSearch"
        :items="platformItems"
        item-title="name"
        item-value="id"
        prefix-label="inline"
        multiple
        chips
        closable-chips
        clearable
        searchable
        :search-placeholder="t('common.search')"
        :placeholder="t('common.all')"
        hide-details
        class="r-v2-missing-fw__platform-select"
      >
        <template #prefix-label>
          <RIcon icon="mdi-controller" size="14" />
          {{ t("common.platform") }}
        </template>
        <template #selection="{ item }">
          <span class="r-v2-missing-fw__platform-chip">
            <CachedPlatformIcon
              :slug="(item.raw as PlatformItem).slug"
              :name="(item.raw as PlatformItem).name"
              :size="14"
            />
            <span>{{ (item.raw as PlatformItem).name }}</span>
          </span>
        </template>
        <template #item="{ props: itemProps, item }">
          <li v-bind="itemProps">
            <CachedPlatformIcon
              :slug="(item.raw as PlatformItem).slug"
              :name="(item.raw as PlatformItem).name"
              :size="20"
            />
            <span class="r-select__item-title">
              {{ (item.raw as PlatformItem).name }}
            </span>
          </li>
        </template>
      </RSelect>
      <div class="r-v2-missing-fw__actions">
        <RTag
          v-if="!loading"
          prepend-icon="mdi-memory"
          :text="rows.length"
          tone="neutral"
        />
        <RMenu location="bottom end" :offset="6" width="240px">
          <template #activator="{ props: activatorProps }">
            <RBtn
              v-bind="activatorProps"
              variant="outlined"
              surface
              icon="mdi-dots-vertical"
              rounded="circle"
              :loading="cleaningUp"
              :aria-label="t('settings.missing-firmware-actions')"
            />
          </template>
          <RMenuItem
            :label="t('settings.cleanup-all')"
            icon="mdi-delete-outline"
            variant="danger"
            :disabled="cleaningUp || showEmpty"
            @click="cleanupAll"
          />
        </RMenu>
      </div>
    </div>

    <div class="r-v2-missing-fw__list">
      <REmptyState
        v-if="showEmpty"
        data-test="missing-firmware-empty"
        icon="mdi-memory"
        :title="t('settings.missing-firmware-none')"
      />

      <ul v-else class="r-v2-missing-fw__rows">
        <li
          v-for="{ firmware, platform } in rows"
          :key="firmware.id"
          data-test="missing-firmware-row"
          class="r-v2-missing-fw__row"
        >
          <RIcon
            icon="mdi-file-question-outline"
            size="16"
            color="var(--r-color-danger-fg)"
          />
          <div class="r-v2-missing-fw__row-body">
            <span class="r-v2-missing-fw__row-name">
              {{ firmware.file_name }}
            </span>
            <span class="r-v2-missing-fw__row-path">
              {{ firmware.file_path }}
            </span>
          </div>
          <span v-if="platform" class="r-v2-missing-fw__row-platform">
            <CachedPlatformIcon
              :slug="platform.slug"
              :name="platform.name"
              :size="16"
            />
            {{ platform.name }}
          </span>
          <span class="r-v2-missing-fw__row-size">
            {{ formatBytes(firmware.file_size_bytes) }}
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.r-v2-missing-fw {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-missing-fw__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-missing-fw__platform-select {
  flex: 1;
  min-width: 0;
  max-width: 480px;
}

.r-v2-missing-fw__platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.r-v2-missing-fw__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.r-v2-missing-fw__list {
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}

.r-v2-missing-fw__rows {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: calc(100dvh - 300px);
  overflow-y: auto;
}

.r-v2-missing-fw__row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-missing-fw__row:last-child {
  border-bottom: 0;
}

.r-v2-missing-fw__row-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-missing-fw__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-muted);
  text-decoration: line-through;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-missing-fw__row-path {
  font-size: 11px;
  color: var(--r-color-fg-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-missing-fw__row-platform {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
}

.r-v2-missing-fw__row-size {
  font-size: 12px;
  color: var(--r-color-fg-faint);
  white-space: nowrap;
}
</style>
