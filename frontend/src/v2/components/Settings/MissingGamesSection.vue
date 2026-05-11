<script setup lang="ts">
// MissingGamesSection — list of ROMs whose files are missing from disk.
// Renders through the shared `RTable` primitive so the visual + sort
// behaviour stays in lock-step with every other table surface in v2;
// the cover-art / metadata cells are slotted in for an at-a-glance
// gallery-style row. Fetches directly via the rom API with
// `filterMissing=true`; manual "Load more" pagination at the bottom.
import {
  RBtn,
  RChip,
  RIcon,
  RSelect,
  RSpinner,
  RTable,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import taskApi from "@/services/api/task";
import storePlatforms from "@/stores/platforms";
import { formatBytes, toBrowserLocale } from "@/utils";
import MoreMenu from "@/v2/components/GameActions/MoreMenu.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import type { SimpleRom } from "@/v2/stores/galleryRoms";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const snackbar = useSnackbar();
const confirm = useConfirm();
const { supportsWebp } = useWebpSupport();

const PAGE_SIZE = 50;

const roms = ref<SimpleRom[]>([]);
const total = ref(0);
const offset = ref(0);
const initialLoading = ref(false);
const loadingMore = ref(false);
const cleaningUp = ref(false);
const selectedPlatformId = ref<number | null>(null);

type SortKey =
  | "name"
  | "fs_size_bytes"
  | "created_at"
  | "first_release_date"
  | "average_rating";

const sortKey = ref<SortKey>("name");
const sortDir = ref<"asc" | "desc">("asc");

const platformItems = computed(() =>
  allPlatforms.value
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((p) => ({ title: p.name, value: p.id })),
);

const hasMore = computed(() => total.value > roms.value.length);

const columns = computed<RTableColumn[]>(() => [
  {
    key: "name",
    label: t("common.name"),
    sortable: true,
    width: "minmax(0, 1.6fr)",
    skeletonWidth: 180,
  },
  {
    key: "platform",
    label: t("common.platform"),
    sortable: false,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "fs_size_bytes",
    label: t("common.size-on-disk"),
    sortable: true,
    width: "100px",
    skeletonWidth: 60,
  },
  {
    key: "created_at",
    label: t("settings.added-header"),
    sortable: true,
    width: "120px",
    skeletonWidth: 80,
  },
  {
    key: "first_release_date",
    label: t("settings.released-header"),
    sortable: true,
    width: "100px",
    skeletonWidth: 60,
  },
  {
    key: "average_rating",
    label: t("settings.rating-header"),
    sortable: true,
    width: "70px",
    align: "end",
    skeletonWidth: 30,
  },
  {
    key: "actions",
    label: "",
    width: "56px",
    align: "end",
    skeletonWidth: 0,
  },
]);

async function fetchPage(concat: boolean) {
  if (loadingMore.value) return;
  if (concat) {
    loadingMore.value = true;
  } else {
    initialLoading.value = true;
    offset.value = 0;
    roms.value = [];
  }
  try {
    const { data } = await romApi.getRoms({
      platformIds: selectedPlatformId.value
        ? [selectedPlatformId.value]
        : null,
      filterMissing: true,
      limit: PAGE_SIZE,
      offset: offset.value,
      orderBy: sortKey.value,
      orderDir: sortDir.value,
      groupByMetaId: false,
    });
    if (data.total !== null && data.total !== undefined) {
      total.value = data.total;
    }
    const items = data.items ?? [];
    roms.value = concat ? [...roms.value, ...items] : items;
    offset.value = roms.value.length;
  } catch (err) {
    snackbar.error(
      t("settings.couldnt-fetch-missing-roms", { error: String(err) }),
    );
  } finally {
    initialLoading.value = false;
    loadingMore.value = false;
  }
}

function onPlatformChange(value: unknown) {
  const id = typeof value === "number" ? value : null;
  selectedPlatformId.value = id;
  void fetchPage(false);
}

function onSort({ key, dir }: RTableSortPayload) {
  if (
    key !== "name" &&
    key !== "fs_size_bytes" &&
    key !== "created_at" &&
    key !== "first_release_date" &&
    key !== "average_rating"
  ) {
    return;
  }
  sortKey.value = key;
  sortDir.value = dir;
  void fetchPage(false);
}

const selectedPlatformName = computed(() => {
  if (!selectedPlatformId.value) return "";
  return platformsStore.get(selectedPlatformId.value)?.name ?? "";
});

async function cleanupAll() {
  const platformLabel = selectedPlatformName.value
    ? ` for ${selectedPlatformName.value}`
    : "";
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.cleanup-all-confirm", { platform: platformLabel }),
    confirmText: t("settings.cleanup-all"),
    tone: "danger",
    requireTyped: "DELETE",
  });
  if (!ok) return;
  cleaningUp.value = true;
  try {
    const body = selectedPlatformId.value
      ? { platform_id: selectedPlatformId.value }
      : {};
    await taskApi.runTask("cleanup_missing_roms", body);
    snackbar.success(t("settings.cleanup-queued"));
    setTimeout(() => void fetchPage(false), 1500);
  } catch (err) {
    snackbar.error(
      t("settings.couldnt-queue-cleanup", { error: String(err) }),
    );
  } finally {
    cleaningUp.value = false;
  }
}

function coverUrl(rom: SimpleRom): string | null {
  const path = rom.path_cover_small ?? rom.path_cover_large ?? null;
  if (!path) return rom.url_cover ?? null;
  return supportsWebp.value
    ? path.replace(/\.(png|jpg|jpeg)$/i, ".webp")
    : path;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString(toBrowserLocale(locale.value), {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function releaseDate(rom: SimpleRom): string {
  const ts = rom.metadatum?.first_release_date;
  if (!ts) return "—";
  return new Date(Number(ts)).toLocaleDateString(
    toBrowserLocale(locale.value),
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    },
  );
}

function ratingValue(rom: SimpleRom): string {
  const r = rom.metadatum?.average_rating;
  if (typeof r !== "number" || r <= 0) return "—";
  return r.toFixed(1);
}

onMounted(() => {
  void fetchPage(false);
});
</script>

<template>
  <div class="r-v2-missing">
    <div class="r-v2-missing__toolbar">
      <RSelect
        :model-value="selectedPlatformId"
        :items="platformItems"
        :disabled="platformItems.length === 0"
        clearable
        hide-details
        prefix-label
        class="r-v2-missing__platform-select"
        @update:model-value="onPlatformChange"
      >
        <template #prefix-label>
          <RIcon icon="mdi-controller" size="14" />
          {{ t("common.platform") }}
        </template>
      </RSelect>
      <RBtn
        variant="flat"
        color="danger"
        prepend-icon="mdi-delete"
        :loading="cleaningUp"
        :disabled="roms.length === 0"
        @click="cleanupAll"
      >
        {{ t("settings.cleanup-all") }}
      </RBtn>
    </div>

    <RTable
      :columns="columns"
      :items="roms"
      :item-key="(r) => (r as SimpleRom).id"
      :loading="initialLoading"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      empty-icon="mdi-folder-question-outline"
      :empty-message="t('settings.missing-games-none')"
      row-height="64px"
      @update:sort="onSort"
    >
      <template #cell.name="{ row }">
        <div class="r-v2-missing__name-cell">
          <div class="r-v2-missing__thumb">
            <img
              v-if="coverUrl(row as SimpleRom)"
              :src="coverUrl(row as SimpleRom) ?? undefined"
              :alt="
                (row as SimpleRom).name ?? (row as SimpleRom).fs_name_no_ext
              "
              loading="lazy"
            />
            <span v-else class="r-v2-missing__thumb-fallback">
              {{
                (
                  (row as SimpleRom).name ?? (row as SimpleRom).fs_name_no_ext
                )
                  .slice(0, 2)
                  .toUpperCase()
              }}
            </span>
          </div>
          <div class="r-v2-missing__name-meta">
            <span class="r-v2-missing__name-title">
              {{ (row as SimpleRom).name ?? (row as SimpleRom).fs_name_no_ext }}
            </span>
            <span class="r-v2-missing__name-fs">
              {{ (row as SimpleRom).fs_name }}
            </span>
          </div>
        </div>
      </template>

      <template #cell.platform="{ row }">
        <span class="r-v2-missing__platform">
          <PlatformIcon
            :slug="
              platformsStore.get((row as SimpleRom).platform_id)?.slug ?? ''
            "
            :size="20"
          />
          <span class="r-v2-missing__platform-name">
            {{ platformsStore.get((row as SimpleRom).platform_id)?.name ?? "—" }}
          </span>
        </span>
      </template>

      <template #cell.fs_size_bytes="{ row }">
        {{
          (row as SimpleRom).fs_size_bytes
            ? formatBytes((row as SimpleRom).fs_size_bytes)
            : "—"
        }}
      </template>

      <template #cell.created_at="{ row }">
        {{ formatDate((row as SimpleRom).created_at) }}
      </template>

      <template #cell.first_release_date="{ row }">
        {{ releaseDate(row as SimpleRom) }}
      </template>

      <template #cell.average_rating="{ row }">
        <RChip v-if="ratingValue(row as SimpleRom) !== '—'" size="x-small">
          {{ ratingValue(row as SimpleRom) }}
        </RChip>
        <span v-else>—</span>
      </template>

      <template #cell.actions="{ row }">
        <MoreMenu :rom="row as SimpleRom">
          <template #activator="{ props: activatorProps }">
            <RBtn
              v-bind="activatorProps"
              variant="text"
              size="small"
              icon
              aria-label="More actions"
            >
              <RIcon icon="mdi-dots-vertical" size="18" />
            </RBtn>
          </template>
        </MoreMenu>
      </template>
    </RTable>

    <div v-if="!initialLoading && hasMore" class="r-v2-missing__load-more">
      <RBtn variant="flat" :loading="loadingMore" @click="fetchPage(true)">
        <span class="r-v2-missing__load-more-label">
          {{ t("gallery.load-more") }}
          <span class="r-v2-missing__load-more-count">
            {{ roms.length }} / {{ total }}
          </span>
        </span>
      </RBtn>
    </div>

    <div v-if="loadingMore && !initialLoading" class="r-v2-missing__pending">
      <RSpinner :size="22" />
    </div>
  </div>
</template>

<style scoped>
.r-v2-missing {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-missing__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-missing__platform-select {
  flex: 1;
  min-width: 0;
  max-width: 360px;
}

/* ----- Name cell — cover thumb + title + filename ----- */
.r-v2-missing__name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.r-v2-missing__thumb {
  width: 36px;
  height: 48px;
  flex-shrink: 0;
  border-radius: var(--r-radius-sm, 4px);
  overflow: hidden;
  background: var(--r-color-surface);
  display: grid;
  place-items: center;
}
.r-v2-missing__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.r-v2-missing__thumb-fallback {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-muted);
}

.r-v2-missing__name-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.r-v2-missing__name-title {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-missing__name-fs {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-family: var(--r-font-family-mono, monospace);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ----- Platform cell ----- */
.r-v2-missing__platform {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.r-v2-missing__platform-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ----- Footer ----- */
.r-v2-missing__load-more {
  display: flex;
  justify-content: center;
}
.r-v2-missing__load-more-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.r-v2-missing__load-more-count {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-v2-missing__pending {
  display: flex;
  justify-content: center;
  padding: 8px;
}
</style>
