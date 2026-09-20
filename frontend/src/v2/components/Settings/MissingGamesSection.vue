<script setup lang="ts">
// MissingGamesSection — Settings tab listing every ROM whose file is
// missing from disk. Shares the gallery's list-mode loading pipeline
// (galleryRoms store + per-row lazy fetch) so a library of any size
// loads in O(viewport) rather than bulk-pulling every match up front.
//
// Wiring: on mount we pin `galleryFilter.filterMissing = true` and clear
// the gallery's selected-platforms (so this tab starts from a known
// state), then bootstrap metadata. The sortable column header and the
// platform multi-select feed the same store inputs the real galleries
// use; delete-all is the only missing-games-specific control, and the
// gallery's SelectionBar carries the bulk actions for a hand-picked set
// (minus download, since these rows point at files that are gone). On
// unmount we restore the caller's filter so the next gallery view they
// land on doesn't inherit `filterMissing=true`.
//
// Layout: a single GameListHeader on top + an RVirtualScroller of
// GameListRow/GameListSkeletonRow items below. The scroller owns its
// own scroll, so the Settings document scroll stays separate.
import {
  RBtn,
  REmptyState,
  RIcon,
  RMenu,
  RMenuItem,
  RSelect,
  RTag,
  RVirtualScroller,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import taskApi from "@/services/api/task";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms, { type Platform } from "@/stores/platforms";
import GameListHeader from "@/v2/components/Gallery/GameListHeader.vue";
import GameListRow from "@/v2/components/Gallery/GameListRow.vue";
import GameListSkeletonRow from "@/v2/components/Gallery/GameListSkeletonRow.vue";
import SelectionBar from "@/v2/components/Gallery/SelectionBar.vue";
import {
  isListSortKey,
  LIST_ROW_HEIGHT_PX,
  type ListSortKey,
} from "@/v2/components/Gallery/listColumns";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useListExpansion } from "@/v2/composables/useListExpansion";
import { useLoadingPhase } from "@/v2/composables/useLoadingPhase";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useTaskCompletion } from "@/v2/composables/useTaskCompletion";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms, { NO_SIDECARS } from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { errorMessage } from "@/v2/utils/errorMessage";

interface PlatformItem {
  id: number;
  slug: string;
  name: string;
}

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const galleryRoms = storeGalleryRoms();
const galleryFilter = storeGalleryFilter();
const platformsStore = storePlatforms();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { awaitTask } = useTaskCompletion();
const { supportsWebp } = useWebpSupport();

const { allPlatforms } = storeToRefs(platformsStore);
const { total, initialFetching, metadataLoaded, orderBy, orderDir } =
  storeToRefs(galleryRoms);
const { selectedPlatforms } = storeToRefs(galleryFilter);

// Caller's filter state captured on mount so we can restore it on
// unmount — leaving `filterMissing=true` active would silently filter
// the next gallery view to missing rows only.
let prevFilterMissing: boolean | null = null;
let prevSelectedPlatforms: Platform[] = [];

const cleaningUp = ref(false);
const platformSearch = ref("");
// The store still holds the previous gallery until onMounted resets it.
const bootstrapped = ref(false);

const phase = useLoadingPhase(
  () => !bootstrapped.value || !metadataLoaded.value || initialFetching.value,
  () => total.value === 0,
);

const platformItems = computed<PlatformItem[]>(() =>
  allPlatforms.value
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((p) => ({ id: p.id, slug: p.slug, name: p.name })),
);

// Bridge between the chip multi-select (id[]) and the gallery filter
// store (Platform[]). Mirrors the pattern used inside `FilterDrawer`
// so the wire format stays consistent across surfaces. Refetch is
// wired through the setter so it fires only on user-driven changes —
// the mount-time reset (`setSelectedFilterPlatforms([])`) writes the
// store directly and skips this path, avoiding a double-bootstrap.
const selectedPlatformIds = computed<number[]>({
  get: () => selectedPlatforms.value.map((p) => p.id),
  set: (ids) => {
    const next = ids
      .map((id) => allPlatforms.value.find((p) => p.id === id))
      .filter((p): p is Platform => !!p);
    galleryFilter.setSelectedFilterPlatforms(next);
    galleryRoms.invalidateWindows();
    void galleryRoms.fetchInitialMetadata(NO_SIDECARS);
  },
});

// The store may carry a key list mode doesn't expose (e.g. `last_played`),
// in which case we paint no active sort.
const listSortKey = computed<ListSortKey | null>(() => {
  const key = orderBy.value;
  return isListSortKey(key) ? key : null;
});

// One entry per absolute position (0 .. total) once metadata is loaded;
// before then, skeleton placeholders once the skeleton is due.
type VItem =
  { kind: "list-row"; position: number } | { kind: "skeleton"; key: number };

const virtualItems = computed<VItem[]>(() => {
  if (!metadataLoaded.value) {
    if (phase.value !== "skeleton") return [];
    return Array.from({ length: 8 }, (_, i) => ({
      kind: "skeleton" as const,
      key: i,
    }));
  }
  const items: VItem[] = [];
  for (let p = 0; p < total.value; p++) {
    items.push({ kind: "list-row", position: p });
  }
  return items;
});

// The rows are the gallery's, detail panel and all, so their heights come
// from the same place.
const listExpansion = useListExpansion();

function vItemHeight(item: unknown): number {
  const v = item as VItem;
  return isListRow(v)
    ? listExpansion.rowHeight(v.position)
    : LIST_ROW_HEIGHT_PX;
}

// The open row's slot is reserved at its settled height; these are the frames
// on the way there (see `useListExpansion`).
const expandedIndex = computed(() => {
  const position = listExpansion.expandedPosition.value;
  if (position == null) return -1;
  return virtualItems.value.findIndex(
    (item) => isListRow(item) && item.position === position,
  );
});
const offsetShift = computed(() =>
  expandedIndex.value < 0
    ? undefined
    : { fromIndex: expandedIndex.value, px: listExpansion.shiftPx.value },
);

interface VListRow {
  kind: "list-row";
  position: number;
}

function isListRow(item: VItem): item is VListRow {
  return item.kind === "list-row";
}

function rowPosition(item: unknown): number {
  const v = item as VItem;
  return isListRow(v) ? v.position : -1;
}

function onListSort({ key, dir }: { key: ListSortKey; dir: "asc" | "desc" }) {
  galleryRoms.setOrderBy(key);
  galleryRoms.setOrderDir(dir);
  galleryRoms.invalidateWindows();
  void galleryRoms.fetchInitialMetadata(NO_SIDECARS);
}

// Viewport-driven windowed fetch. Unlike the real gallery this section
// owns the scroller directly (no GalleryShell), so it must translate the
// scroller's visible range into window fetches itself — otherwise every
// row's `getRomAt(position)` stays null and the list shows skeletons
// forever. Mirrors GalleryShell's debounced sync + re-sync-on-items-change.
const FETCH_DEBOUNCE_MS = 80;
let fetchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
const viewportRange = ref<{ first: number; last: number }>({
  first: 0,
  last: -1,
});

function collectVisiblePositions(range: {
  first: number;
  last: number;
}): Set<number> {
  const out = new Set<number>();
  if (range.last < range.first) return out;
  const items = virtualItems.value;
  for (let i = range.first; i <= range.last; i++) {
    const it = items[i];
    if (it && it.kind === "list-row") out.add(it.position);
  }
  return out;
}

function syncFetches(range: { first: number; last: number }) {
  galleryRoms.syncVisibleWindows(collectVisiblePositions(range));
}

function onViewportRange(range: { first: number; last: number }) {
  viewportRange.value = range;
  if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
  fetchDebounceTimer = setTimeout(() => {
    fetchDebounceTimer = null;
    syncFetches(range);
  }, FETCH_DEBOUNCE_MS);
}

// Metadata resolving flips `virtualItems` from skeleton placeholders to
// real list-rows without necessarily changing the visible index range
// (rows 0..N are visible in both), so the scroller may not re-emit. Sync
// immediately against the current viewport so the first window loads.
watch(virtualItems, () => {
  listExpansion.collapse();
  if (fetchDebounceTimer) {
    clearTimeout(fetchDebounceTimer);
    fetchDebounceTimer = null;
  }
  syncFetches(viewportRange.value);
});

const selectedPlatformsLabel = computed(() =>
  selectedPlatforms.value.map((p) => p.name).join(", "),
);

async function cleanupAll() {
  const platformLabel = selectedPlatformsLabel.value
    ? ` ${t("common.for")} ${selectedPlatformsLabel.value}`
    : "";
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.cleanup-all-confirm", { platform: platformLabel }),
    confirmText: t("settings.missing-games-delete-all"),
    tone: "danger",
    requireTyped: "DELETE",
  });
  if (!ok) return;
  cleaningUp.value = true;
  try {
    const body = selectedPlatforms.value.length
      ? { platform_ids: selectedPlatforms.value.map((p) => p.id) }
      : {};
    const { data } = await taskApi.runTask("cleanup_missing_roms", body);
    snackbar.success(t("settings.cleanup-queued"));
    if (await awaitTask(data.task_id)) {
      galleryRoms.invalidateWindows();
      await galleryRoms.fetchInitialMetadata(NO_SIDECARS);
    }
  } catch (err) {
    snackbar.error(
      t("settings.couldnt-queue-cleanup", { error: errorMessage(err) }),
    );
  } finally {
    cleaningUp.value = false;
  }
}

onMounted(() => {
  prevFilterMissing = galleryFilter.filterMissing;
  prevSelectedPlatforms = galleryFilter.selectedPlatforms.slice();
  galleryRoms.resetGallery();
  galleryFilter.setFilterMissing(true);
  galleryFilter.setSelectedFilterPlatforms([]);
  galleryRoms.setOrderBy("name");
  galleryRoms.setOrderDir("asc");
  bootstrapped.value = true;
  void galleryRoms.fetchInitialMetadata(NO_SIDECARS);
});

onBeforeUnmount(() => {
  if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
  galleryFilter.setFilterMissing(prevFilterMissing);
  galleryFilter.setSelectedFilterPlatforms(prevSelectedPlatforms);
  galleryRoms.resetGallery();
  // Selection is surface-scoped: drop it so the next gallery's
  // SelectionBar doesn't resurface picks made on this tab.
  storeGallerySelection().clear();
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
      <div class="r-v2-missing__actions">
        <RTag
          v-if="metadataLoaded"
          prepend-icon="mdi-folder-question-outline"
          :text="total.toLocaleString()"
          tone="neutral"
          class="r-v2-missing__count"
        />
        <RMenu location="bottom end" :offset="6" width="220px">
          <template #activator="{ props: activatorProps }">
            <RBtn
              v-bind="activatorProps"
              variant="outlined"
              surface
              icon="mdi-dots-vertical"
              rounded="circle"
              :loading="cleaningUp"
              :aria-label="t('settings.missing-games-actions')"
            />
          </template>
          <RMenuItem
            :label="t('settings.missing-games-delete-all')"
            icon="mdi-delete-outline"
            variant="danger"
            :disabled="cleaningUp || phase !== 'content'"
            @click="cleanupAll"
          />
        </RMenu>
      </div>
    </div>

    <REmptyState
      v-if="phase === 'empty'"
      icon="mdi-folder-question-outline"
      :title="t('settings.missing-games-none')"
    />
    <div v-else-if="phase !== 'idle'" class="r-v2-missing__list">
      <GameListHeader
        :sort-key="listSortKey"
        :sort-dir="orderDir"
        @sort="onListSort"
      />
      <RVirtualScroller
        :items="virtualItems"
        :get-item-height="vItemHeight"
        :offset-shift="offsetShift"
        :overscan="25"
        class="r-v2-missing__scroller"
        @update:viewport-range="onViewportRange"
      >
        <template #default="{ item }">
          <GameListRow
            v-if="isListRow(item as VItem)"
            :position="rowPosition(item)"
            :webp="supportsWebp"
            expandable
            :expanded="listExpansion.isExpanded(rowPosition(item))"
            :detail-height="listExpansion.panelHeight(rowPosition(item))"
            @toggle-expand="listExpansion.toggle(rowPosition(item))"
          />
          <GameListSkeletonRow v-else />
        </template>
      </RVirtualScroller>
    </div>

    <SelectionBar hide-download />
  </div>
</template>

<style scoped>
.r-v2-missing {
  display: flex;
  flex-direction: column;
  gap: 14px;
  /* Definite (NOT min-) height. `height: 100%` on `RVirtualScroller`'s
     wrapper resolves against the parent's `height` per the CSS spec —
     `min-height` doesn't count, the percentage falls back to `auto` and
     the scroller's `overflow-y` never engages, so every row mounts at
     once. Same trick GalleryShell uses with `height: calc(100vh - nav-h)`.
     The subtraction adds up the chrome Settings stacks above this
     section (nav 58 + content padding-top 32 + body padding-top 18 +
     RTabNav band ~60) and leaves a bottom gap matching the horizontal
     padding (~58px = 40px content + 18px body) so the list's bottom
     edge reads as the visual sibling of its left/right edges. The
     section's bottom overshoots `body`'s inner-bottom by ~20px, which
     consumes part of `.r-v2-settings__content`'s `padding-bottom: 60px`
     — content intrinsic still fits within `min-height: 100vh - nav-h`
     so the page doesn't grow a document scroll. */
  height: calc(100dvh - 226px);
  min-height: 320px;
}

.r-v2-missing__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.r-v2-missing__platform-select {
  flex: 1;
  min-width: 0;
  max-width: 480px;
}

.r-v2-missing__platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* Right cluster: count chip + kebab menu. `margin-left: auto` pushes
   the group to the trailing edge regardless of how much horizontal
   slack the platform-select absorbs. */
.r-v2-missing__actions {
  display: flex;
  align-self: stretch;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

/* Stretched to the toolbar row and pill-shaped to pair with the kebab. */
.r-v2-missing__count {
  align-self: stretch;
  border-radius: var(--r-radius-pill);
}

/* List frame — the column header sits at the top, the virtualiser
   takes the remaining height. `min-height: 0` is load-bearing: without
   it the flex child would refuse to shrink below its scroll content
   and the scroller would grow the whole page instead of clipping. */
.r-v2-missing__list {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}

.r-v2-missing__scroller {
  flex: 1;
  min-height: 0;
}
</style>
