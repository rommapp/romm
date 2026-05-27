<script setup lang="ts">
// PlatformsIndex — full grid of every platform, with the same toolbar
// (search / groupBy / layout) the ROM galleries use. Toolbar state lives
// in `useGalleryMode` so toggling layout here also affects Platform /
// Collection / Search ROM views — one consistent reading mode across
// every main surface. Search is local (per-view URL ?search=) since the
// platforms list is small enough that no Pinia store is warranted.
//
// Group-by axes: "letter" (universal across galleries) plus three
// platform-specific modes — "family" (PlayStation / Nintendo / …),
// "category" (Console / Portable / Computer / …), "generation" (1st /
// 2nd / …). Each non-letter mode is implemented as the same shape:
// list of `{ label, items: Platform[] }` buckets the template iterates
// blindly. When the global groupBy lands on a value with no usable
// data on the loaded platforms, the view falls through to flat — the
// toolbar's mode is the user's intent, not a hard requirement.
import { RDivider, RLetterHeading, RSkeletonBlock } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storePlatforms, { type Platform } from "@/stores/platforms";
import GalleryToolbar, {
  type GroupByItem,
} from "@/v2/components/Gallery/GalleryToolbar.vue";
import PlatformListHeader from "@/v2/components/Platforms/PlatformListHeader.vue";
import PlatformListRow from "@/v2/components/Platforms/PlatformListRow.vue";
import PlatformTile from "@/v2/components/Platforms/PlatformTile.vue";
import {
  platformGenerationLabel,
  type PlatformSortKey,
  prettifyPlatformCategory,
} from "@/v2/components/Platforms/platformListColumns";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import IndexShell from "@/v2/components/shared/IndexShell.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useGalleryMode } from "@/v2/composables/useGalleryMode";
import { useGalleryViewModeUrl } from "@/v2/composables/useGalleryViewModeUrl";
import { usePlatformPlayableChecker } from "@/v2/composables/usePlatformPlayable";
import { useTileSearchUrl } from "@/v2/composables/useTileSearchUrl";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";

const { t } = useI18n();
const platformsStore = storePlatforms();
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);

const { groupBy, layout } = useGalleryMode();
useGalleryViewModeUrl();
const searchTerm = useTileSearchUrl();
const { isPlayable } = usePlatformPlayableChecker();

// Spatial 2D arrow / gamepad nav across the wrapping tiles grid. List-mode
// rows are anchor-based and tab through natively; the spatial nav only
// targets `.plat-tile` in grid mode (which is the only place tiles render
// — list mode emits `.plat-list-row`).
const gridRoot = ref<HTMLElement | null>(null);
useWrapGridNav(gridRoot, { cellSelector: ".plat-tile" });

// Pre-compute the playable flag per platform — sort comparator and
// every row read this map so the column, the badge on the tile, and
// the playable bucket all agree on a single source of truth.
const playableById = computed(() => {
  const fn = isPlayable.value;
  const map = new Map<number | string, boolean>();
  for (const p of filledPlatforms.value) map.set(p.id, fn(p.slug));
  return map;
});

// Two independent sort states. The list view's column headers drive
// `listSortKey` + `listSortDir`; the grid view's toolbar asc/desc toggle
// drives `gridSortDir`, with the implicit axis tied to the active
// groupBy (letter → name, family → family, …, none → name). Keeping
// them separate so flipping one mode doesn't reshuffle the other.
const listSortKey = ref<PlatformSortKey>("name");
const listSortDir = ref<"asc" | "desc">("asc");
const gridSortDir = ref<"asc" | "desc">("asc");

function onListSort({
  key,
  dir,
}: {
  key: PlatformSortKey;
  dir: "asc" | "desc";
}) {
  listSortKey.value = key;
  listSortDir.value = dir;
}

// Sort axis the grid view should use, derived from the active groupBy.
// Grid has no column headers — the bucket axis is the natural sort axis,
// the toolbar asc/desc toggle is the only direction control.
const gridSortKey = computed<PlatformSortKey>(() => {
  switch (groupBy.value) {
    case "family":
      return "family";
    case "category":
      return "category";
    case "generation":
      return "generation";
    case "playable":
      return "playable";
    default:
      return "name";
  }
});

// Pure comparator parameterised by (key, dir). Both sort states feed it
// to produce their respective sorted arrays. `name` is the secondary
// tiebreaker for every other column so equal values still land in a
// stable alphabetical order.
function compareBy(
  a: Platform,
  b: Platform,
  key: PlatformSortKey,
  dir: "asc" | "desc",
): number {
  const sign = dir === "asc" ? 1 : -1;
  const byName = a.display_name.localeCompare(b.display_name);
  switch (key) {
    case "name":
      return byName * sign;
    case "family": {
      const af = a.family_name ?? "";
      const bf = b.family_name ?? "";
      const cmp = af.localeCompare(bf);
      return (cmp || byName) * sign;
    }
    case "category": {
      const ac = a.category ?? "";
      const bc = b.category ?? "";
      const cmp = ac.localeCompare(bc);
      return (cmp || byName) * sign;
    }
    case "generation": {
      const ag = a.generation ?? -1;
      const bg = b.generation ?? -1;
      const cmp = ag - bg;
      return (cmp || byName) * sign;
    }
    case "playable": {
      const ap = playableById.value.get(a.id) ? 1 : 0;
      const bp = playableById.value.get(b.id) ? 1 : 0;
      const cmp = ap - bp;
      return (cmp || byName) * sign;
    }
    case "rom_count": {
      const ar = a.rom_count ?? 0;
      const br = b.rom_count ?? 0;
      const cmp = ar - br;
      return (cmp || byName) * sign;
    }
  }
}

// Toolbar group-by items — order = visual order in the segmented
// slider (28×28 each, so 5 items still fits the toolbar comfortably on
// desktop). Tooltips ride on `title`.
const platformGroupByItems: GroupByItem[] = [
  {
    id: "none",
    icon: "mdi-view-agenda-outline",
    ariaLabel: "Flat view",
    title: "Flat view",
  },
  {
    id: "letter",
    icon: "mdi-alphabetical-variant",
    ariaLabel: "Group by letter",
    title: "Group by letter",
  },
  {
    id: "family",
    icon: "mdi-family-tree",
    ariaLabel: "Group by family",
    title: "Group by family",
  },
  {
    id: "category",
    icon: "mdi-shape-outline",
    ariaLabel: "Group by category",
    title: "Group by category",
  },
  {
    id: "generation",
    icon: "mdi-numeric",
    ariaLabel: "Group by generation",
    title: "Group by generation",
  },
  {
    id: "playable",
    icon: "mdi-play-circle-outline",
    ariaLabel: "Group by playable",
    title: "Group by playable",
  },
];

onMounted(() => {
  if (platformsStore.allPlatforms.length === 0) {
    platformsStore.fetchPlatforms();
  }
});

const filtered = computed<Platform[]>(() => {
  const term = searchTerm.value.trim().toLowerCase();
  if (!term) return filledPlatforms.value;
  return filledPlatforms.value.filter((p) =>
    p.display_name.toLowerCase().includes(term),
  );
});

// Per-mode sorted views. Grid uses the toolbar asc/desc + groupBy axis;
// list uses the column-header click state. Buckets are always fed the
// grid-sorted array (Map iteration preserves insertion order, so items
// inside each bucket inherit that order).
const sortedForGrid = computed<Platform[]>(() => {
  return [...filtered.value].sort((a, b) =>
    compareBy(a, b, gridSortKey.value, gridSortDir.value),
  );
});
const sortedForList = computed<Platform[]>(() => {
  return [...filtered.value].sort((a, b) =>
    compareBy(a, b, listSortKey.value, listSortDir.value),
  );
});

const totalCount = computed(() => filledPlatforms.value.length);
const noResults = computed(
  () =>
    !fetchingPlatforms.value &&
    totalCount.value > 0 &&
    filtered.value.length === 0,
);

// Generic bucket — every grouping computed produces the same shape so
// the template can iterate one branch per non-letter mode. `key` is the
// raw bucket discriminator (sortable); `label` is what we show.
type Bucket = { key: string; label: string; items: Platform[] };

function bucketBy(
  items: Platform[],
  pick: (p: Platform) => { key: string; label: string },
  sort: (a: Bucket, b: Bucket) => number,
): Bucket[] {
  // `items` is pre-sorted by the active column (see `sorted` computed);
  // Array.push + Map iteration both preserve insertion order, so items
  // inside each bucket inherit that sort.
  const map = new Map<string, Bucket>();
  for (const p of items) {
    const { key, label } = pick(p);
    const bucket = map.get(key);
    if (bucket) bucket.items.push(p);
    else map.set(key, { key, label, items: [p] });
  }
  return [...map.values()].sort(sort);
}

// Letter buckets. Non-letter first chars split into two head buckets so
// the user can tell digits apart from other symbols at a glance:
//   * "#" — digits (0-9)
//   * "@" — anything else (Greek, punctuation, etc.)
// Order in asc: `# A…Z @` — `#` first, `@` last (matches AlphaStrip's
// ALPHABET). Desc flips the whole sequence (`@ Z…A #`).
const BUCKET_ORDER = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ@";
const letterGroups = computed<Bucket[]>(() => {
  const dirSign = gridSortDir.value === "asc" ? 1 : -1;
  return bucketBy(
    sortedForGrid.value,
    (p) => {
      const ch = p.display_name.charAt(0).toUpperCase();
      if (/[A-Z]/.test(ch)) return { key: ch, label: ch };
      if (/[0-9]/.test(ch)) return { key: "#", label: "#" };
      return { key: "@", label: "@" };
    },
    (a, b) =>
      (BUCKET_ORDER.indexOf(a.key) - BUCKET_ORDER.indexOf(b.key)) * dirSign,
  );
});

// Family buckets. `family_slug` is the stable id (cheap to use as a
// Map key); `family_name` is what the user reads. Platforms without a
// family land in "Other" and sort last.
const familyGroups = computed<Bucket[]>(() =>
  bucketBy(
    sortedForGrid.value,
    (p) => {
      const slug = p.family_slug;
      const name = p.family_name;
      if (slug && name) return { key: slug, label: name };
      return { key: "__other", label: "Other" };
    },
    (a, b) => {
      if (a.key === "__other") return 1;
      if (b.key === "__other") return -1;
      return a.label.localeCompare(b.label);
    },
  ),
);

// Category buckets. IGDB raw values come through as snake_case
// ("portable_console", "operating_system") — `prettifyPlatformCategory`
// (shared with PlatformListRow's metadata column) produces a human
// label without altering the underlying key.
const categoryGroups = computed<Bucket[]>(() =>
  bucketBy(
    sortedForGrid.value,
    (p) => {
      const c = p.category;
      if (c) return { key: c, label: prettifyPlatformCategory(c) };
      return { key: "__other", label: "Other" };
    },
    (a, b) => {
      if (a.key === "__other") return 1;
      if (b.key === "__other") return -1;
      return a.label.localeCompare(b.label);
    },
  ),
);

// Generation buckets. Sorted ascending; null lands in "Unknown" at
// the end. Labels use English ordinals via the shared helper so the
// list-mode metadata column and the group heading agree word-for-word.
const generationGroups = computed<Bucket[]>(() =>
  bucketBy(
    sortedForGrid.value,
    (p) => {
      const g = p.generation;
      if (typeof g === "number" && g > 0) {
        // Pad the key so string sort puts "9" before "10".
        return {
          key: g.toString().padStart(4, "0"),
          label: platformGenerationLabel(g),
        };
      }
      return { key: "__unknown", label: "Unknown generation" };
    },
    (a, b) => {
      if (a.key === "__unknown") return 1;
      if (b.key === "__unknown") return -1;
      return a.key.localeCompare(b.key);
    },
  ),
);

// Playable buckets. Two groups in a fixed order ("Playable" first, then
// "Not playable") so the user always sees the affirmative bucket on
// top regardless of sort direction.
const playableGroups = computed<Bucket[]>(() =>
  bucketBy(
    sortedForGrid.value,
    (p) =>
      playableById.value.get(p.id)
        ? { key: "playable", label: "Playable" }
        : { key: "not_playable", label: "Not playable" },
    (a, b) => (a.key === "playable" ? -1 : b.key === "playable" ? 1 : 0),
  ),
);

// Active bucket list per groupBy mode. When the chosen mode produces
// only one group ("Other" / "Unknown"), the rendering still works —
// it's just one labelled section, no different from a flat grid with
// a label on top. The visual answers the user's intent without us
// needing to second-guess.
const groupedBuckets = computed<Bucket[] | null>(() => {
  if (layout.value !== "grid") return null;
  switch (groupBy.value) {
    case "letter":
      return letterGroups.value;
    case "family":
      return familyGroups.value;
    case "category":
      return categoryGroups.value;
    case "generation":
      return generationGroups.value;
    case "playable":
      return playableGroups.value;
    default:
      return null;
  }
});
</script>

<template>
  <IndexShell :list-mode="layout === 'list'">
    <template #header>
      <PageHeader :title="t('common.platforms')" :count="totalCount" />
      <RDivider class="r-v2-pidx__header-divider" />
    </template>

    <template #toolbar>
      <GalleryToolbar
        :group-by="groupBy"
        :layout="layout"
        :sort-dir="gridSortDir"
        :search="searchTerm"
        :group-by-items="platformGroupByItems"
        show-search
        :search-placeholder="t('platform.search-platform')"
        @update:group-by="groupBy = $event"
        @update:layout="layout = $event"
        @update:sort-dir="gridSortDir = $event"
        @update:search="searchTerm = $event"
      />
    </template>

    <template #listHeader>
      <PlatformListHeader
        :sort-key="listSortKey"
        :sort-dir="listSortDir"
        @sort="onListSort"
      />
    </template>

    <div ref="gridRoot">
      <div v-if="fetchingPlatforms && !totalCount" class="r-v2-pidx__grid">
        <RSkeletonBlock
          v-for="n in 16"
          :key="`sk-${n}`"
          width="100%"
          height="140px"
          rounded="card"
        />
      </div>

      <EmptyState
        v-else-if="!totalCount"
        :message="t('platform.no-platforms-empty')"
      />

      <EmptyState
        v-else-if="noResults"
        :message="t('platform.no-platforms-search', { query: searchTerm })"
      />

      <!-- List mode — rows underneath the sticky column header (rendered
           by IndexShell via the `#listHeader` slot above). Rows surface
           the same family / category / generation axes the toolbar can
           group by, so the user reading the flat list still sees what
           would have separated them. -->
      <div v-else-if="layout === 'list'" class="r-v2-pidx__list">
        <PlatformListRow
          v-for="p in sortedForList"
          :key="p.id"
          :id="p.id"
          :slug="p.slug"
          :fs-slug="p.fs_slug"
          :display-name="p.display_name"
          :rom-count="p.rom_count"
          :family-name="p.family_name ?? null"
          :category="p.category ?? null"
          :generation="p.generation ?? null"
        />
      </div>

      <!-- Grid mode, grouped — letter uses RLetterHeading (large
           single-character glyph); family / category / generation use
           a compact section heading so multi-word labels read cleanly. -->
      <div v-else-if="groupedBuckets">
        <template v-for="g in groupedBuckets" :key="g.key">
          <RLetterHeading v-if="groupBy === 'letter'" :label="g.label" />
          <h3 v-else class="r-v2-pidx__group-heading">{{ g.label }}</h3>
          <div class="r-v2-pidx__grid">
            <PlatformTile
              v-for="p in g.items"
              :id="p.id"
              :key="p.id"
              :slug="p.slug"
              :fs-slug="p.fs_slug"
              :display-name="p.display_name"
              :rom-count="p.rom_count"
              variant="grid"
            />
          </div>
        </template>
      </div>

      <!-- Grid mode, flat. -->
      <div v-else class="r-v2-pidx__grid">
        <PlatformTile
          v-for="p in sortedForGrid"
          :id="p.id"
          :key="p.id"
          :slug="p.slug"
          :fs-slug="p.fs_slug"
          :display-name="p.display_name"
          :rom-count="p.rom_count"
          variant="grid"
        />
      </div>
    </div>
  </IndexShell>
</template>

<style scoped>
/* Mirror the gallery shell's header→toolbar separator so the visual
   rhythm matches Search / Platform / Collection ROM views. */
.r-v2-pidx__header-divider {
  margin-bottom: 16px;
}

.r-v2-pidx__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
}

.r-v2-pidx__list :deep(.plat-list-row:last-child) {
  border-bottom: 0;
}

/* Section heading used by family / category / generation grouping —
   compact uppercase label with the same vocabulary as
   RLetterHeading's metadata, so the two heading styles read as
   siblings instead of competing surfaces. The single bottom margin
   creates breathing room above the grid; vertical rhythm between
   sibling sections lives on the heading's `margin-top`. */
.r-v2-pidx__group-heading {
  margin: 24px 0 12px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}
.r-v2-pidx__group-heading:first-child {
  margin-top: 4px;
}

html[data-bp~="xs"] .r-v2-pidx__grid {
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 10px;
}
</style>
