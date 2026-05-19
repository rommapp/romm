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
import { computed, onMounted } from "vue";
import storePlatforms, { type Platform } from "@/stores/platforms";
import GalleryToolbar, {
  type GroupByItem,
} from "@/v2/components/Gallery/GalleryToolbar.vue";
import PlatformListHeader from "@/v2/components/Platforms/PlatformListHeader.vue";
import PlatformListRow from "@/v2/components/Platforms/PlatformListRow.vue";
import PlatformTile from "@/v2/components/Platforms/PlatformTile.vue";
import {
  platformGenerationLabel,
  prettifyPlatformCategory,
} from "@/v2/components/Platforms/platformListColumns";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useGalleryMode } from "@/v2/composables/useGalleryMode";
import { useGalleryViewModeUrl } from "@/v2/composables/useGalleryViewModeUrl";
import { useTileSearchUrl } from "@/v2/composables/useTileSearchUrl";

const platformsStore = storePlatforms();
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);

const { groupBy, layout } = useGalleryMode();
useGalleryViewModeUrl();
const searchTerm = useTileSearchUrl();

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
  const map = new Map<string, Bucket>();
  for (const p of items) {
    const { key, label } = pick(p);
    const bucket = map.get(key);
    if (bucket) bucket.items.push(p);
    else map.set(key, { key, label, items: [p] });
  }
  // Sort items inside each bucket alphabetically — the user reads each
  // bucket as its own mini-grid and expects A→Z within it.
  for (const bucket of map.values()) {
    bucket.items.sort((a, b) => a.display_name.localeCompare(b.display_name));
  }
  return [...map.values()].sort(sort);
}

// Letter buckets. Non-alpha first chars roll up under "#" so Greek /
// numeric / symbol-prefixed platform names still land in a stable
// section.
const letterGroups = computed<Bucket[]>(() =>
  bucketBy(
    filtered.value,
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
    filtered.value,
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
    filtered.value,
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
    filtered.value,
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
    default:
      return null;
  }
});
</script>

<template>
  <section class="r-v2-pidx">
    <PageHeader title="Platforms" :count="totalCount" />

    <RDivider class="r-v2-pidx__header-divider" />

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

    <!-- List mode — rows underneath a sticky-style column header.
         Rows surface the same family / category / generation axes
         the toolbar can group by, so the user reading the flat list
         still sees what would have separated them. -->
    <div v-else-if="layout === 'list'" class="r-v2-pidx__list">
      <PlatformListHeader />
      <PlatformListRow
        v-for="p in filtered"
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
        v-for="p in filtered"
        :id="p.id"
        :key="p.id"
        :slug="p.slug"
        :fs-slug="p.fs_slug"
        :display-name="p.display_name"
        :rom-count="p.rom_count"
        variant="grid"
      />
    </div>
  </section>
</template>

<style scoped>
.r-v2-pidx {
  padding: 32px var(--r-row-pad) 60px;
}

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

html[data-bp~="xs"] .r-v2-pidx {
  padding: 16px 14px 80px;
}
html[data-bp~="xs"] .r-v2-pidx__grid {
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 10px;
}
</style>
