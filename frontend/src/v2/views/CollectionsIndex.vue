<script setup lang="ts">
// CollectionsIndex — full grid of every collection (regular + smart +
// virtual). Same toolbar (search / groupBy / layout) the ROM galleries
// use, with state shared via `useGalleryMode` so toggling layout here
// also flips it on the rest of the gallery surfaces. Search is local
// (per-view URL ?search=) — the collections list is small enough that
// no Pinia store is warranted.
//
// Visual hierarchy: regular + smart collections live inside a
// translucent panel (mirrors the related-games surface in the game
// detail view) so the user reads them as one cohesive "real" group.
// Virtual collections render loose below the panel so the difference
// between curated/computed and dynamic-grouping collections is obvious
// at a glance. The kind filter (toolbar slider) narrows this further to
// one group when the user wants to focus.
import { RDivider, RLetterHeading, RSkeletonBlock, RIcon } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import CollectionListHeader from "@/v2/components/Collections/CollectionListHeader.vue";
import CollectionListRow from "@/v2/components/Collections/CollectionListRow.vue";
import CollectionTile from "@/v2/components/Collections/CollectionTile.vue";
import GalleryToolbar, {
  type KindFilterItem,
  type KindFilterValue,
} from "@/v2/components/Gallery/GalleryToolbar.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import IndexShell from "@/v2/components/shared/IndexShell.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useGalleryMode } from "@/v2/composables/useGalleryMode";
import { useGalleryViewModeUrl } from "@/v2/composables/useGalleryViewModeUrl";
import { useTileSearchUrl } from "@/v2/composables/useTileSearchUrl";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

type AnyCollection = Collection | VirtualCollection | SmartCollection;
type Kind = "regular" | "virtual" | "smart";
type CollectionTileEntry = {
  id: string | number;
  name: string;
  rom_count: number;
  covers: string[];
  link: string;
  kind: Kind;
};

const collectionsStore = storeCollections();
const { toWebp } = useWebpSupport();
const {
  allCollections,
  virtualCollections,
  smartCollections,
  fetchingCollections,
} = storeToRefs(collectionsStore);

const { groupBy, layout } = useGalleryMode();
useGalleryViewModeUrl();
const searchTerm = useTileSearchUrl();
const gridSortDir = ref<"asc" | "desc">("asc");

// `?kind=` URL-synced filter — same direction rules as
// `useTileSearchUrl`: route → ref on every change, ref → router.replace
// on user input, no history entry per click. "all" is the default and
// is omitted from the URL so a clean link doesn't carry a redundant
// query param.
const route = useRoute();
const router = useRouter();
const VALID_KINDS: readonly KindFilterValue[] = ["all", "regular", "virtual"];
function readKindFromQuery(): KindFilterValue {
  const v = route.query.kind;
  return typeof v === "string" && (VALID_KINDS as readonly string[]).includes(v)
    ? (v as KindFilterValue)
    : "all";
}
const kindFilter = ref<KindFilterValue>(readKindFromQuery());
watch(
  () => route.query.kind,
  () => {
    const next = readKindFromQuery();
    if (next !== kindFilter.value) kindFilter.value = next;
  },
);
watch(kindFilter, (next) => {
  const desired = next === "all" ? undefined : next;
  const current = readKindFromQuery();
  if ((desired ?? "all") === current) return;
  const nextQuery = { ...route.query };
  if (desired === undefined) delete nextQuery.kind;
  else nextQuery.kind = desired;
  router.replace({ query: nextQuery });
});

// Icon-only in segmented mode (the slider's btns are 28×28 — labels
// would overflow); the kebab menu falls back to `title` when `label`
// is absent so the names still surface there.
const kindFilterItems: KindFilterItem[] = [
  {
    id: "all",
    icon: "mdi-bookmark-multiple",
    ariaLabel: "All collections",
    title: "All collections",
  },
  {
    id: "regular",
    icon: "mdi-bookmark-outline",
    ariaLabel: "Curated collections",
    title: "Curated collections",
  },
  {
    id: "virtual",
    icon: "mdi-bookmark-box",
    ariaLabel: "Virtual collections",
    title: "Virtual collections",
  },
];

onMounted(() => {
  if (allCollections.value.length === 0) collectionsStore.fetchCollections();
  if (smartCollections.value.length === 0) {
    collectionsStore.fetchSmartCollections();
  }
  if (virtualCollections.value.length === 0) {
    const type =
      localStorage.getItem("settings.virtualCollectionType") ?? "collection";
    collectionsStore.fetchVirtualCollections(type);
  }
});

function coversFor(c: AnyCollection): string[] {
  const paths = (c as { path_covers_small?: string[] }).path_covers_small ?? [];
  return paths.slice(0, 4).map(toWebp);
}

const tiles = computed<CollectionTileEntry[]>(() => {
  const out: CollectionTileEntry[] = [];
  for (const c of allCollections.value) {
    out.push({
      id: c.id,
      name: c.name,
      rom_count: c.rom_count,
      covers: coversFor(c),
      link: `/collection/${c.id}`,
      kind: "regular",
    });
  }
  for (const c of smartCollections.value) {
    out.push({
      id: c.id,
      name: c.name,
      rom_count: c.rom_count,
      covers: coversFor(c),
      link: `/collection/smart/${c.id}`,
      kind: "smart",
    });
  }
  for (const c of virtualCollections.value) {
    out.push({
      id: c.id,
      name: c.name,
      rom_count: c.rom_count,
      covers: coversFor(c),
      link: `/collection/virtual/${c.id}`,
      kind: "virtual",
    });
  }
  return out;
});

const filtered = computed<CollectionTileEntry[]>(() => {
  const term = searchTerm.value.trim().toLowerCase();
  const byTerm = !term
    ? tiles.value
    : tiles.value.filter((c) => c.name.toLowerCase().includes(term));
  if (kindFilter.value === "regular") {
    return byTerm.filter((c) => c.kind !== "virtual");
  }
  if (kindFilter.value === "virtual") {
    return byTerm.filter((c) => c.kind === "virtual");
  }
  return byTerm;
});

// Sort comparator for grid mode — the toolbar asc/desc toggle drives
// direction, name is the only sort axis the grid surface exposes.
function gridCompare(a: CollectionTileEntry, b: CollectionTileEntry): number {
  const sign = gridSortDir.value === "asc" ? 1 : -1;
  return a.name.localeCompare(b.name) * sign;
}

// Curated = regular + smart (both real, hand-managed). Virtual is the
// dynamic/computed kind. Splitting up front keeps every render branch
// (flat / letter / list) free of inline kind checks.
const curatedTiles = computed<CollectionTileEntry[]>(() =>
  [...filtered.value.filter((c) => c.kind !== "virtual")].sort(gridCompare),
);
const virtualTiles = computed<CollectionTileEntry[]>(() =>
  [...filtered.value.filter((c) => c.kind === "virtual")].sort(gridCompare),
);

const totalCount = computed(() => tiles.value.length);
const noResults = computed(
  () =>
    !fetchingCollections.value &&
    totalCount.value > 0 &&
    filtered.value.length === 0,
);

type LetterGroup = { letter: string; items: CollectionTileEntry[] };
// Bucket visual order in asc: `# A…Z @` — `#` (digits) first, `@`
// (other symbols) last; mirrors AlphaStrip's ALPHABET. Desc flips the
// whole sequence (`@ Z…A #`).
const COLLECTION_BUCKET_ORDER = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ@";
function groupByLetter(items: CollectionTileEntry[]): LetterGroup[] {
  // `items` is pre-sorted by `gridCompare` (see curatedTiles /
  // virtualTiles); Array.push + Map iteration preserve insertion order
  // so items inside each bucket inherit that direction.
  //
  // Non-letter first chars split into two distinct buckets so digits
  // and other symbols read as separate sections:
  //   * "#" — digits (0-9)
  //   * "@" — anything else
  const map = new Map<string, CollectionTileEntry[]>();
  for (const c of items) {
    const ch = c.name.charAt(0).toUpperCase();
    let key: string;
    if (/[A-Z]/.test(ch)) key = ch;
    else if (/[0-9]/.test(ch)) key = "#";
    else key = "@";
    const bucket = map.get(key);
    if (bucket) bucket.push(c);
    else map.set(key, [c]);
  }
  const dirSign = gridSortDir.value === "asc" ? 1 : -1;
  return [...map.entries()]
    .sort(
      ([a], [b]) =>
        (COLLECTION_BUCKET_ORDER.indexOf(a) -
          COLLECTION_BUCKET_ORDER.indexOf(b)) *
        dirSign,
    )
    .map(([letter, items]) => ({ letter, items }));
}
const curatedLetterGroups = computed<LetterGroup[]>(() =>
  groupByLetter(curatedTiles.value),
);
const virtualLetterGroups = computed<LetterGroup[]>(() =>
  groupByLetter(virtualTiles.value),
);

const showLetterGroups = computed(
  () => layout.value === "grid" && groupBy.value === "letter",
);

// Whether to show each section. The translucent "curated" panel only
// renders in grid mode (it's a grid-mode visual element); list mode
// stays flat with the kind column carrying the distinction.
const showCuratedSection = computed(
  () => layout.value === "grid" && curatedTiles.value.length > 0,
);
const showVirtualSection = computed(
  () => layout.value === "grid" && virtualTiles.value.length > 0,
);
</script>

<template>
  <IndexShell :list-mode="layout === 'list'">
    <template #header>
      <PageHeader title="Collections" :count="totalCount" />
      <RDivider class="r-v2-cidx__header-divider" />
    </template>

    <template #toolbar>
      <GalleryToolbar
        :group-by="groupBy"
        :layout="layout"
        :sort-dir="gridSortDir"
        :search="searchTerm"
        show-search
        search-placeholder="Search collections"
        show-kind-filter
        :kind-filter="kindFilter"
        :kind-filter-items="kindFilterItems"
        kind-filter-aria-label="Filter collections"
        @update:group-by="groupBy = $event"
        @update:layout="layout = $event"
        @update:sort-dir="gridSortDir = $event"
        @update:search="searchTerm = $event"
        @update:kind-filter="kindFilter = $event"
      />
    </template>

    <template #listHeader>
      <CollectionListHeader />
    </template>

    <div v-if="fetchingCollections && !totalCount" class="r-v2-cidx__grid">
      <RSkeletonBlock
        v-for="n in 12"
        :key="`sk-${n}`"
        width="100%"
        height="150px"
        rounded="lg"
      />
    </div>

    <EmptyState
      v-else-if="!totalCount"
      message="You don't have any collections yet. Favourite a game or create one from any ROM's action bar to populate this view."
    />

    <EmptyState
      v-else-if="noResults"
      :message="`No collections match “${searchTerm}”.`"
    />

    <div v-else-if="layout === 'list'" class="r-v2-cidx__list">
      <CollectionListRow
        v-for="c in filtered"
        :id="c.id"
        :key="`${c.kind}-${c.id}`"
        :to="c.link"
        :name="c.name"
        :rom-count="c.rom_count"
        :covers="c.covers"
        :kind="c.kind"
      />
    </div>

    <template v-else>
      <!-- Curated panel — regular + smart in a translucent container,
           mirroring the related-games panel surface in the game detail
           view. Stays out of the way when nothing curated matches. -->
      <section v-if="showCuratedSection" class="r-v2-cidx__panel">
        <h3 class="r-v2-cidx__panel-title">
          <RIcon icon="mdi-bookmark" class="r-v2-cidx__panel-icon" />Curated
        </h3>
        <template v-if="showLetterGroups">
          <template v-for="g in curatedLetterGroups" :key="`cur-${g.letter}`">
            <RLetterHeading :label="g.letter" />
            <div class="r-v2-cidx__grid">
              <CollectionTile
                v-for="c in g.items"
                :id="c.id"
                :key="`${c.kind}-${c.id}`"
                :to="c.link"
                :name="c.name"
                :rom-count="c.rom_count"
                :covers="c.covers"
                :kind="c.kind"
                variant="grid"
              />
            </div>
          </template>
        </template>
        <div v-else class="r-v2-cidx__grid">
          <CollectionTile
            v-for="c in curatedTiles"
            :id="c.id"
            :key="`${c.kind}-${c.id}`"
            :to="c.link"
            :name="c.name"
            :rom-count="c.rom_count"
            :covers="c.covers"
            :kind="c.kind"
            variant="grid"
          />
        </div>
      </section>

      <!-- Virtual section — loose grid, no panel. The visual absence of
           a container is the contrast point against the curated panel
           above. -->
      <section v-if="showVirtualSection" class="r-v2-cidx__virtual">
        <h3 v-if="showCuratedSection" class="r-v2-cidx__section-title">
          <RIcon icon="mdi-bookmark-box" class="r-v2-cidx__panel-icon" />Virtual
        </h3>
        <template v-if="showLetterGroups">
          <template v-for="g in virtualLetterGroups" :key="`vir-${g.letter}`">
            <RLetterHeading :label="g.letter" />
            <div class="r-v2-cidx__grid">
              <CollectionTile
                v-for="c in g.items"
                :id="c.id"
                :key="`${c.kind}-${c.id}`"
                :to="c.link"
                :name="c.name"
                :rom-count="c.rom_count"
                :covers="c.covers"
                :kind="c.kind"
                variant="grid"
              />
            </div>
          </template>
        </template>
        <div v-else class="r-v2-cidx__grid">
          <CollectionTile
            v-for="c in virtualTiles"
            :id="c.id"
            :key="`${c.kind}-${c.id}`"
            :to="c.link"
            :name="c.name"
            :rom-count="c.rom_count"
            :covers="c.covers"
            :kind="c.kind"
            variant="grid"
          />
        </div>
      </section>
    </template>
  </IndexShell>
</template>

<style scoped>
/* Mirror the gallery shell's header→toolbar separator so the visual
   rhythm matches Search / Platform / Collection ROM views. */
.r-v2-cidx__header-divider {
  margin-bottom: 16px;
}

.r-v2-cidx__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 20px 16px;
}

.r-v2-cidx__list :deep(.coll-list-row:last-child) {
  border-bottom: 0;
}

/* Curated panel — translucent container (same vocabulary as the
   related-games surface in the game detail view via RCollapsible).
   Acts as the visual "this is one cohesive group" cue against the
   loose virtual section that follows. */
.r-v2-cidx__panel {
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  padding: 18px 20px 22px;
  margin-bottom: 24px;
}

/* Section heading — small uppercase label at the top of each kind
   block. Same scale/weight as the related-games inner headings. */
.r-v2-cidx__panel-title,
.r-v2-cidx__section-title {
  margin: 0 0 14px 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

.r-v2-cidx__panel-icon {
  margin-right: var(--r-space-2);
  color: var(--r-color-fg-muted);
}

html[data-bp~="xs"] .r-v2-cidx__grid {
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 16px 10px;
}
html[data-bp~="xs"] .r-v2-cidx__panel {
  padding: 14px 14px 18px;
}
</style>
