<script setup lang="ts">
// MissingGamesSection — list of ROMs whose files are missing from disk.
// Renders through the shared `RTable` primitive so the visual + sort
// behaviour stays in lock-step with every other table surface in v2;
// the cover-art / metadata cells are slotted in for an at-a-glance
// gallery-style row.
//
// Load model: all missing ROMs are pulled into memory on mount via
// paginated batches (the backend caps `limit`, so we loop until
// `data.total` is reached or the page comes back short). With the
// full set in memory, platform filter and sort are pure client-side
// operations on `filteredRoms` — instant, no refetch.
import {
  RBtn,
  RChip,
  RIcon,
  RPlatformIcon,
  RSelect,
  RTable,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import taskApi from "@/services/api/task";
import storePlatforms from "@/stores/platforms";
import { formatBytes, toBrowserLocale } from "@/utils";
import MoreMenu from "@/v2/components/GameActions/MoreMenu.vue";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import type { SimpleRom } from "@/v2/stores/galleryRoms";

interface PlatformItem {
  id: number;
  slug: string;
  name: string;
}

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const snackbar = useSnackbar();
const confirm = useConfirm();
const { supportsWebp } = useWebpSupport();

// Batch size for the bulk load. Backend caps `limit` server-side; we
// loop in batches until we've covered `data.total` (or the page comes
// back short). Sized generously so most libraries finish in one shot.
const FETCH_BATCH = 500;

const roms = ref<SimpleRom[]>([]);
const initialLoading = ref(false);
const cleaningUp = ref(false);
const selectedPlatformIds = ref<number[]>([]);
const platformSearch = ref("");

type SortKey =
  | "name"
  | "fs_size_bytes"
  | "created_at"
  | "first_release_date"
  | "average_rating";

const sortKey = ref<SortKey>("name");
const sortDir = ref<"asc" | "desc">("asc");

// Selector items are derived directly from the loaded `roms` — since
// we hold every missing ROM in memory, the set is complete and
// stable for the lifetime of the section. Picking a platform doesn't
// change the option set (we filter `filteredRoms`, not `roms`).
const platformItems = computed<PlatformItem[]>(() => {
  const ids = new Set<number>();
  for (const r of roms.value) {
    if (r.platform_id != null) ids.add(r.platform_id);
  }
  return allPlatforms.value
    .filter((p) => ids.has(p.id))
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((p) => ({ id: p.id, slug: p.slug, name: p.name }));
});

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

// Bulk-load every missing ROM into memory. Loops in `FETCH_BATCH`-
// sized pages so a backend `limit` cap can't truncate us silently —
// stops as soon as a short page arrives (means we've reached the
// end) or once `data.total` is covered.
async function fetchAll() {
  if (initialLoading.value) return;
  initialLoading.value = true;
  try {
    const acc: SimpleRom[] = [];
    let offset = 0;
    let total: number | null = null;
    while (true) {
      const { data } = await romApi.getRoms({
        filterMissing: true,
        limit: FETCH_BATCH,
        offset,
        orderBy: "name",
        orderDir: "asc",
        groupByMetaId: false,
      });
      if (data.total != null) total = data.total;
      const items = data.items ?? [];
      acc.push(...items);
      offset += items.length;
      if (items.length < FETCH_BATCH) break;
      if (total != null && offset >= total) break;
    }
    roms.value = acc;
  } catch (err) {
    snackbar.error(
      t("settings.couldnt-fetch-missing-roms", { error: String(err) }),
    );
  } finally {
    initialLoading.value = false;
  }
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
}

// Filter + sort happen entirely in memory now — the full `roms` set
// is hydrated once on mount, then we derive the table data from it.
function compareRoms(a: SimpleRom, b: SimpleRom): number {
  const dir = sortDir.value === "asc" ? 1 : -1;
  switch (sortKey.value) {
    case "name": {
      const an = a.name ?? a.fs_name_no_ext ?? "";
      const bn = b.name ?? b.fs_name_no_ext ?? "";
      return an.localeCompare(bn) * dir;
    }
    case "fs_size_bytes":
      return ((a.fs_size_bytes ?? 0) - (b.fs_size_bytes ?? 0)) * dir;
    case "created_at": {
      const at = a.created_at ? Date.parse(a.created_at) : 0;
      const bt = b.created_at ? Date.parse(b.created_at) : 0;
      return (at - bt) * dir;
    }
    case "first_release_date": {
      const at = Number(a.metadatum?.first_release_date ?? 0);
      const bt = Number(b.metadatum?.first_release_date ?? 0);
      return (at - bt) * dir;
    }
    case "average_rating": {
      const ar = a.metadatum?.average_rating ?? 0;
      const br = b.metadatum?.average_rating ?? 0;
      return (ar - br) * dir;
    }
    default:
      return 0;
  }
}

const filteredRoms = computed<SimpleRom[]>(() => {
  let r = roms.value;
  if (selectedPlatformIds.value.length > 0) {
    const set = new Set(selectedPlatformIds.value);
    r = r.filter((rom) => rom.platform_id != null && set.has(rom.platform_id));
  }
  return [...r].sort(compareRoms);
});

// Confirmation label for cleanup — lists every selected platform's
// name, joined by commas. Empty string when nothing is filtered.
const selectedPlatformsLabel = computed(() =>
  selectedPlatformIds.value
    .map((id) => platformsStore.get(id)?.name)
    .filter((n): n is string => !!n)
    .join(", "),
);

async function cleanupAll() {
  const platformLabel = selectedPlatformsLabel.value
    ? ` for ${selectedPlatformsLabel.value}`
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
    // The task API takes a single `platform_id`. With multi-select on,
    // the safe path is: send the id only when exactly one is picked
    // (so cleanup matches the user's intent on a narrow filter);
    // otherwise run unfiltered cleanup across all platforms.
    const body =
      selectedPlatformIds.value.length === 1
        ? { platform_id: selectedPlatformIds.value[0] }
        : {};
    await taskApi.runTask("cleanup_missing_roms", body);
    snackbar.success(t("settings.cleanup-queued"));
    setTimeout(() => void fetchAll(), 1500);
  } catch (err) {
    snackbar.error(t("settings.couldnt-queue-cleanup", { error: String(err) }));
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
  void fetchAll();
});
</script>

<template>
  <div class="r-v2-missing">
    <div class="r-v2-missing__toolbar">
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
        class="r-v2-missing__platform-select"
      >
        <template #prefix-label>
          <RIcon icon="mdi-controller" size="14" />
          {{ t("common.platform") }}
        </template>
        <template #selection="{ item }">
          <span class="r-v2-missing__platform-chip">
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
      :items="filteredRoms"
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
                ((row as SimpleRom).name ?? (row as SimpleRom).fs_name_no_ext)
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
          <RPlatformIcon
            :slug="
              platformsStore.get((row as SimpleRom).platform_id)?.slug ?? ''
            "
            :size="20"
          />
          <span class="r-v2-missing__platform-name">
            {{
              platformsStore.get((row as SimpleRom).platform_id)?.name ?? "—"
            }}
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
/* Platform multi-select takes the toolbar's left side; the
   cleanup-all button sits to its right. `flex: 1` lets the field
   absorb the toolbar's horizontal slack; `max-width` keeps it from
   eating the whole row on very wide screens. */
.r-v2-missing__platform-select {
  flex: 1;
  min-width: 0;
  max-width: 480px;
}

/* Each chip in the multi-select shows the platform icon + name in a
   compact pill — RSelect provides the chip surface, we only style the
   inner span layout. */
.r-v2-missing__platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
</style>
