<script setup lang="ts">
// Collection gallery — thin orchestrator around `GalleryShell`. Owns
// the regular/virtual/smart collection load flow and fills the shell's
// `#header` slot with a CollectionMosaic-fronted InfoPanel.
import { RChip } from "@v2/lib";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import Stat from "@/v2/components/shared/Stat.vue";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

type AnyCollection = Collection | VirtualCollection | SmartCollection;
type CollectionKind = "regular" | "virtual" | "smart";

const route = useRoute();
const collectionsStore = storeCollections();
const galleryRoms = storeGalleryRoms();
const { toWebp } = useWebpSupport();

const notFound = ref(false);
const currentKind = ref<CollectionKind>("regular");
const currentCollection = ref<AnyCollection | null>(null);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);

const mosaicCovers = computed<string[]>(() => {
  const paths =
    (currentCollection.value as { path_covers_small?: string[] } | null)
      ?.path_covers_small ?? [];
  return paths.slice(0, 4).map(toWebp);
});

const description = computed(
  () =>
    (currentCollection.value as { description?: string | null } | null)
      ?.description ?? "",
);

const kindLabel = computed(() => {
  if (currentKind.value === "virtual") return "Virtual collection";
  if (currentKind.value === "smart") return "Smart collection";
  return "Collection";
});

function kindFromRoute(
  name: string | symbol | null | undefined,
): CollectionKind {
  if (name === "virtual-collection") return "virtual";
  if (name === "smart-collection") return "smart";
  return "regular";
}

async function ensureLoaded(kind: CollectionKind) {
  if (kind === "regular" && collectionsStore.allCollections.length === 0) {
    await collectionsStore.fetchCollections();
  } else if (
    kind === "virtual" &&
    collectionsStore.virtualCollections.length === 0
  ) {
    const type =
      localStorage.getItem("settings.virtualCollectionType") ?? "collection";
    await collectionsStore.fetchVirtualCollections(type);
  } else if (
    kind === "smart" &&
    collectionsStore.smartCollections.length === 0
  ) {
    await collectionsStore.fetchSmartCollections();
  }
}

function findById(kind: CollectionKind, id: string): AnyCollection | undefined {
  if (kind === "regular") {
    return collectionsStore.allCollections.find((c) => String(c.id) === id);
  }
  if (kind === "virtual") {
    return collectionsStore.virtualCollections.find((c) => String(c.id) === id);
  }
  return collectionsStore.smartCollections.find((c) => String(c.id) === id);
}

async function loadForRoute(kind: CollectionKind, id: string) {
  currentKind.value = kind;
  await ensureLoaded(kind);
  const collection = findById(kind, id);
  if (!collection) {
    notFound.value = true;
    currentCollection.value = null;
    return;
  }
  notFound.value = false;
  currentCollection.value = collection;

  // Switching collection — full reset of the gallery store.
  galleryRoms.resetGallery();
  if (kind === "regular") {
    galleryRoms.setCurrentCollection(collection as Collection);
  } else if (kind === "virtual") {
    galleryRoms.setCurrentVirtualCollection(collection as VirtualCollection);
  } else {
    galleryRoms.setCurrentSmartCollection(collection as SmartCollection);
  }

  document.title = collection.name;
  // Bootstrap metadata only; grid (shell viewport-sync) and list
  // (GameListRow's onMounted) both hydrate rows per-position from here.
  await galleryRoms.fetchInitialMetadata();
  await nextTick();
  shellRef.value?.applyRestoredScroll();
}

onMounted(() => {
  loadForRoute(kindFromRoute(route.name), String(route.params.collection));
});

onBeforeRouteUpdate((to) => {
  // Shell saves the previous route's scroll automatically before this
  // guard runs.
  loadForRoute(kindFromRoute(to.name), String(to.params.collection));
});

watch(
  () => [route.name, route.params.collection] as const,
  ([name, id]) => {
    if (id == null) return;
    loadForRoute(kindFromRoute(name), String(id));
  },
);
</script>

<template>
  <GalleryShell
    ref="shellRef"
    :has-header="!!currentCollection"
    search-placeholder="Filter this collection…"
    empty-message="This collection is empty."
    :not-found="notFound"
    not-found-message="Collection not found."
    :skeleton-row-count="4"
  >
    <!-- HEADER (Section 1) — collection InfoPanel: 4-cover mosaic +
         eyebrow ("Collection" / "Virtual collection" / "Smart
         collection") + name + optional description chip + ROM count.
         Shell auto-measures the slot's height, so the toolbar's natural
         offset matches the InfoPanel's rendered bottom edge. -->
    <template #header>
      <InfoPanel v-if="currentCollection" :title="currentCollection.name">
        <template #cover>
          <div
            class="r-v2-coll__panel-cover"
            :style="{
              viewTransitionName: `coll-cover-${currentKind}-${currentCollection.id}`,
            }"
          >
            <CollectionMosaic :covers="mosaicCovers" aspect-ratio="140 / 188" />
          </div>
        </template>
        <template #eyebrow>
          <span class="r-eyebrow">{{ kindLabel }}</span>
        </template>
        <template v-if="description" #tags>
          <RChip size="small" variant="translucent" :rounded="20">
            {{ description }}
          </RChip>
        </template>
        <template #stats>
          <Stat :value="currentCollection.rom_count" label="Games" />
        </template>
      </InfoPanel>
    </template>
  </GalleryShell>
</template>

<style scoped>
.r-v2-coll__panel-cover {
  width: 140px;
  height: 188px;
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  box-shadow: var(--r-elev-2);
}

html[data-bp~="xs"] .r-v2-coll__panel-cover {
  width: 100px;
  height: 134px;
}
</style>
