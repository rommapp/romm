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

const platformsStore = storePlatforms();
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);

const { groupBy, layout } = useGalleryMode();
useGalleryViewModeUrl();
const searchTerm = useTileSearchUrl();
const { isPlayable } = usePlatformPlayableChecker();

// Pre-compute the playable flag per platform — sort comparator and
// every row read this map so the column, the badge on the tile, and
// the playable bucket all agree on a single source of truth.
const playableById = computed(() => {
  const fn = isPlayable.value;
  const map = new Map<number | string, boolean>();
  for (const p of filledPlatforms.value) map.set(p.id, fn(p.slug));
  return map;
});

// Sort state — local to this view (the platforms index is small enough
// that a URL round-trip is overkill; debt item if/when we make this
// bookmarkable).
const sortKey = ref<PlatformSortKey>("name");
const sortDir = ref<"asc" | "desc">("asc");

function onSort({ key, dir }: { key: PlatformSortKey; dir: "asc" | "desc" }) {
  sortKey.value = key;
  sortDir.value = dir;
}

// Comparator pulled out so the flat list and each bucket can share it.
// `name` is the secondary tiebreaker for every other column so equal
// values still land in a stable alphabetical order.
function compare(a: Platform, b: Platform): number {
  const dir = sortDir.value === "asc" ? 1 : -1;
  const byName = a.display_name.localeCompare(b.display_name);
  switch (sortKey.value) {
    case "name":
      return byName * dir;
    case "family": {
      const af = a.family_name ?? "";
      const bf = b.family_name ?? "";
      const cmp = af.localeCompare(bf);
      return (cmp || byName) * dir;
    }
    case "category": {
      const ac = a.category ?? "";
      const bc = b.category ?? "";
      const cmp = ac.localeCompare(bc);
      return (cmp || byName) * dir;
    }
    case "generation": {
      const ag = a.generation ?? -1;
      const bg = b.generation ?? -1;
      const cmp = ag - bg;
      return (cmp || byName) * dir;
    }
    case "playable": {
      const ap = playableById.value.get(a.id) ? 1 : 0;
      const bp = playableById.value.get(b.id) ? 1 : 0;
      const cmp = ap - bp;
      return (cmp || byName) * dir;
    }
    case "rom_count": {
      const ar = a.rom_count ?? 0;
      const br = b.rom_count ?? 0;
      const cmp = ar - br;
      return (cmp || byName) * dir;
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

// Sorted view of the filtered list. Single source of truth feeding both
// the flat layouts and the bucket builders (which preserve insertion
// order, so items inside each bucket inherit this sort).
const sorted = computed<Platform[]>(() => {
  return [...filtered.value].sort(compare);
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

// Letter buckets. Non-alpha first chars roll up under "#" so Greek /
// numeric / symbol-prefixed platform names still land in a stable
// section.
const letterGroups = computed<Bucket[]>(() =>
  bucketBy(
    sorted.value,
    (p) => {
      const ch = p.display_name.charAt(0).toUpperCase();
      const key = /[A-Z]/.test(ch) ? ch : "#";
      return { key, label: key };
    },
    (a, b) => {
      // "#" sorts after letters so the alphabetical run is unbroken.
      if (a.key === "#") return 1;
      if (b.key === "#") return -1;
      return a.key.localeCompare(b.key);
    },
  ),
);

// Family buckets. `family_slug` is the stable id (cheap to use as a
// Map key); `family_name` is what the user reads. Platforms without a
// family land in "Other" and sort last.
const familyGroups = computed<Bucket[]>(() =>
  bucketBy(
    sorted.value,
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
    sorted.value,
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
    sorted.value,
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
    sorted.value,
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
      <PageHeader title="Platforms" :count="totalCount" />
      <RDivider class="r-v2-pidx__header-divider" />
    </template>

    <template #toolbar>
      <GalleryToolbar
        :group-by="groupBy"
        :layout="layout"
        :search="searchTerm"
        :group-by-items="platformGroupByItems"
        show-search
        search-placeholder="Search platforms"
        @update:group-by="groupBy = $event"
        @update:layout="layout = $event"
        @update:search="searchTerm = $event"
      />
    </template>

    <template #listHeader>
      <PlatformListHeader
        :sort-key="sortKey"
        :sort-dir="sortDir"
        @sort="onSort"
      />
    </template>

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
      message="No platforms found. Run a scan to populate your library."
    />

    <EmptyState
      v-else-if="noResults"
      :message="`No platforms match “${searchTerm}”.`"
    />

    <!-- List mode — rows underneath the sticky column header (rendered
         by IndexShell via the `#listHeader` slot above). Rows surface
         the same family / category / generation axes the toolbar can
         group by, so the user reading the flat list still sees what
         would have separated them. -->
    <div v-else-if="layout === 'list'" class="r-v2-pidx__list">
      <PlatformListRow
        v-for="p in sorted"
        :key="p.id"
        :id="p.id"
        :slug="p.slug"
        :fs-slug="p.fs_slug"
        :display-name="p.display_name"
        :rom-count="p.rom_count"
        :family-name="p.family_name ?? null"
        :category="p.category ?? null"
        :generation="p.generation ?? null"
        :playable="playableById.get(p.id) ?? false"
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
        v-for="p in sorted"
        :id="p.id"
        :key="p.id"
        :slug="p.slug"
        :fs-slug="p.fs_slug"
        :display-name="p.display_name"
        :rom-count="p.rom_count"
        variant="grid"
      />
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
