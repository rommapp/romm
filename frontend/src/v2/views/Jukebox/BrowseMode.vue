<script setup lang="ts">
// One facet-driven browse screen: artist / genre / platform / decade / album
// differ only by the facet they load and the filter they hand the track query.
import {
  RIcon,
  RList,
  RListItem,
  RPlatformIcon,
  RSkeletonBlock,
  RTextField,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import musicApi, { type MusicTrackFilters } from "@/services/api/music";
import useMusicFavorites from "@/stores/musicFavorites";
import SoundtrackPanel from "@/v2/components/Soundtrack/Panel.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import { useTrackPager } from "@/v2/composables/useTrackPager";
import { panelTracksFromCatalog } from "@/v2/utils/soundtrackTracks";

export interface BrowseEntry {
  key: string;
  label: string;
  count: number;
  /** Platform rows show the console badge instead of a generic glyph. */
  platformSlug?: string;
  coverUrl?: string;
  subtitle?: string;
}

const props = defineProps<{
  icon: string;
  /** Loads the sidebar list. `search` is only passed when `searchable`. */
  loadEntries: (search: string) => Promise<BrowseEntry[]>;
  /** Turns the picked entry into a server-side track filter. */
  filterFor: (key: string) => MusicTrackFilters;
  selected: string;
  /** Bumped by the host to force a refetch (e.g. after a delete). */
  refreshToken?: number;
  searchable?: boolean;
  startShuffled?: boolean;
  deletable?: boolean;
}>();
const emit = defineEmits<{
  (e: "update:selected", key: string): void;
  (e: "delete-track", fileId: number, romId: number): void;
}>();

const { t } = useI18n();
const favorites = useMusicFavorites();

const entries = ref<BrowseEntry[]>([]);
const loadingEntries = ref(true);
const entriesFailed = ref(false);
const search = ref("");

const pager = useTrackPager((items) => favorites.merge(items));

let entriesToken = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

async function loadEntries(term: string) {
  const token = ++entriesToken;
  loadingEntries.value = true;
  entriesFailed.value = false;
  try {
    const next = await props.loadEntries(term);
    if (token !== entriesToken) return;
    entries.value = next;
    // Keep the URL's pick when it still exists, else fall back to the first.
    const stillThere = next.some((entry) => entry.key === props.selected);
    if (!stillThere) emit("update:selected", next[0]?.key ?? "");
  } catch {
    if (token === entriesToken) entriesFailed.value = true;
  } finally {
    if (token === entriesToken) loadingEntries.value = false;
  }
}

function loadTracks(key: string) {
  if (!key) return pager.reset(null);
  const filters = props.filterFor(key);
  return pager.reset(async (offset, limit) => {
    const { data } = await musicApi.getTracks({ ...filters, offset, limit });
    return { items: data.items, total: data.total };
  });
}

watch(search, (term) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => void loadEntries(term.trim()), 250);
});

watch(
  [() => props.selected, () => props.refreshToken],
  ([key]) => void loadTracks(key),
  { immediate: true },
);

// A delete also changes the sidebar's counts, and may empty the picked
// entry entirely (loadEntries then falls back to the first one).
watch(
  () => props.refreshToken,
  () => void loadEntries(search.value.trim()),
);

void loadEntries("");

const panelTracks = computed(() => panelTracksFromCatalog(pager.tracks.value));

function onDelete(fileId: number, romId: number) {
  emit("delete-track", fileId, romId);
}
</script>

<template>
  <aside class="jukebox__sidebar">
    <div v-if="searchable" class="jukebox__sidebar-head">
      <RTextField
        v-model="search"
        prepend-inner-icon="mdi-magnify"
        :placeholder="t('common.search')"
        clearable
        hide-details
        density="compact"
      />
    </div>

    <div class="jukebox__entries r-v2-scroll-hidden">
      <template v-if="loadingEntries">
        <RSkeletonBlock v-for="n in 7" :key="n" height="60px" rounded="md" />
      </template>
      <EmptyState
        v-else-if="entriesFailed"
        :icon="icon"
        :message="t('common.unknown-error')"
      />
      <EmptyState
        v-else-if="!entries.length"
        :icon="icon"
        :message="t('common.no-results')"
      />
      <RList v-else density="default">
        <RListItem
          v-for="entry in entries"
          :key="entry.key"
          :title="entry.label"
          :subtitle="entry.subtitle"
          :active="selected === entry.key"
          :aria-label="entry.label"
          @click="emit('update:selected', entry.key)"
        >
          <template #prepend>
            <div class="jukebox__entry-icon">
              <img
                v-if="entry.coverUrl"
                :src="entry.coverUrl"
                alt=""
                loading="lazy"
              />
              <RPlatformIcon
                v-else-if="entry.platformSlug"
                :slug="entry.platformSlug"
                :alt="entry.label"
                size="100%"
                :show-tooltip="false"
              />
              <RIcon v-else :icon="icon" size="22" />
            </div>
          </template>
          <template #append>
            <span class="jukebox__entry-count">{{ entry.count }}</span>
          </template>
        </RListItem>
      </RList>
    </div>
  </aside>

  <main class="jukebox__main">
    <SoundtrackPanel
      :key="selected"
      :tracks="panelTracks"
      :loading="pager.loading.value"
      :loading-more="pager.loadingMore.value"
      :total-tracks="pager.total.value"
      :start-shuffled="startShuffled"
      :deletable="deletable"
      :empty-icon="icon"
      wide
      class="jukebox__player"
      @reached="pager.loadMoreIfNear"
      @delete-track="onDelete"
    />
  </main>
</template>

<style scoped>
.jukebox__sidebar {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--r-color-border);
  background: color-mix(in srgb, var(--r-color-bg-elevated) 70%, transparent);
}

.jukebox__sidebar-head {
  padding: 14px 16px;
  border-bottom: 1px solid var(--r-color-border);
}

.jukebox__entries {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.jukebox__entry-icon {
  width: 42px;
  height: 56px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-cover-placeholder);
  color: var(--r-color-fg-muted);
}

.jukebox__entry-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.jukebox__entry-count {
  min-width: 24px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.jukebox__main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.jukebox__player {
  height: 100%;
}

html[data-bp~="xs"] .jukebox__sidebar-head {
  display: none;
}

html[data-bp~="xs"] .jukebox__entries {
  padding: 8px;
}

html[data-bp~="xs"] .jukebox__entries :deep(.r-list-item) {
  justify-content: center;
  padding: 6px;
}

html[data-bp~="xs"] .jukebox__entries :deep(.r-list-item__body),
html[data-bp~="xs"] .jukebox__entries :deep(.r-list-item__append) {
  display: none;
}

html[data-bp~="xs"] .jukebox__player :deep(.r-v2-stp__row-duration),
html[data-bp~="xs"] .jukebox__player :deep(.r-v2-stp__row-size) {
  display: none;
}
</style>
