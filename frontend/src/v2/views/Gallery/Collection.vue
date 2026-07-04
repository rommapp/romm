<script setup lang="ts">
// Collection view — owns the regular / virtual / smart collection
// load flow and the two-tab surface that sits above the gallery:
//   • Library  — the gallery (delegated to `GalleryShell`).
//   • Settings — `CollectionSettingsTab` (cover artwork + details +
//     smart criteria + danger zone). Hidden for virtual collections
//     since they have no editable fields.
//
// Layout choice mirrors `Platform.vue`: `CollectionHead` (InfoPanel +
// RTabNav) lives INSIDE the scrolling container of whichever branch
// is active. On Library, it rides in `GalleryShell`'s `#header` slot
// so it scrolls away with the cards (toolbar pins below it). On
// Settings, it sits in a plain scroll wrapper above the tab body.
//
// Edit + Delete moved out of the InfoPanel `#actions` kebab and into
// the Settings tab (editable form on top, danger zone at the bottom).
import { RDivider, type RTabNavItem } from "@v2/lib";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import CollectionHead from "@/v2/components/Gallery/CollectionHead.vue";
import CollectionSettingsTab from "@/v2/components/Gallery/CollectionSettingsTab.vue";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { collectionCoverList } from "@/v2/utils/collectionCovers";

type AnyCollection = Collection | VirtualCollection | SmartCollection;
type CollectionKind = "regular" | "virtual" | "smart";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = storeAuth();
const confirm = useConfirm();
const snackbar = useSnackbar();
const collectionsStore = storeCollections();
const galleryRoms = storeGalleryRoms();
const { toWebp } = useWebpSupport();

const notFound = ref(false);
const currentKind = ref<CollectionKind>("regular");
const currentCollection = ref<AnyCollection | null>(null);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);
const deleting = ref(false);
const canDownload = useCan("rom.download");

// Virtual collections are computed (no editable fields) — only
// regular / smart get the Settings tab.
const editableKind = computed<"regular" | "smart" | null>(() => {
  if (currentKind.value === "regular") return "regular";
  if (currentKind.value === "smart") return "smart";
  return null;
});

// Ownership gate for the Settings tab. v1 only renders the drawer's
// edit/delete affordances for owners with `collections.write` — if the
// user can do neither, hide the tab entirely so they don't land on an
// inert form. Mirrors the gate the tab body re-applies internally.
const isOwner = computed(() => {
  const c = currentCollection.value as { user_id?: number | null } | null;
  return !!c && c.user_id != null && c.user_id === auth.user?.id;
});
const showSettingsTab = computed(
  () =>
    !!editableKind.value &&
    isOwner.value &&
    auth.scopes.includes("collections.write"),
);

// Narrowed reference for the Settings tab — `editableKind` rules out
// the virtual branch, so we can hand a `Collection | SmartCollection`
// to the tab without per-template casts.
const editableCollection = computed<Collection | SmartCollection | null>(() =>
  editableKind.value
    ? (currentCollection.value as Collection | SmartCollection)
    : null,
);

// ── Tabs ─────────────────────────────────────────────────────────
// URL-persistent via `?tab=` (mirrors Platform / GameDetails). Virtual
// collections never see the Settings tab — clamp invalid persisted
// values back to `library`.
type TabId = "library" | "settings";
const VALID_TABS = new Set<TabId>(["library", "settings"]);

function parseTab(v: unknown): TabId {
  if (typeof v !== "string") return "library";
  if (!VALID_TABS.has(v as TabId)) return "library";
  if (v === "settings" && !showSettingsTab.value) return "library";
  return v as TabId;
}

const tab = ref<TabId>(parseTab(route.query.tab));
watch(tab, (value) => {
  if (route.query.tab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, tab: value },
    });
  }
});
watch(
  () => route.query.tab,
  (value) => {
    const next = parseTab(value);
    if (next !== tab.value) tab.value = next;
  },
);
// Switching to a virtual collection (no Settings tab) while sitting on
// `settings` — bounce back to Library so the user isn't staring at an
// empty body.
watch(showSettingsTab, (allowed) => {
  if (!allowed && tab.value === "settings") tab.value = "library";
});

const tabs = computed<RTabNavItem[]>(() => {
  const out: RTabNavItem[] = [{ id: "library", label: t("common.library") }];
  if (showSettingsTab.value) {
    out.push({ id: "settings", label: t("collection.settings") });
  }
  return out;
});

function onTabChange(next: string) {
  tab.value = parseTab(next);
}

function onSaved(updated: Collection | SmartCollection) {
  currentCollection.value = updated;
}

const mosaicCovers = computed<string[]>(() => {
  const c = currentCollection.value as {
    path_cover_small?: string | null;
    path_covers_small?: string[];
  } | null;
  if (!c) return [];
  return collectionCoverList(c, toWebp);
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

  galleryRoms.resetGallery();
  if (kind === "regular") {
    galleryRoms.setCurrentCollection(collection as Collection);
  } else if (kind === "virtual") {
    galleryRoms.setCurrentVirtualCollection(collection as VirtualCollection);
  } else {
    galleryRoms.setCurrentSmartCollection(collection as SmartCollection);
  }

  document.title = collection.name;
  await galleryRoms.fetchInitialMetadata();
  await nextTick();
  shellRef.value?.applyRestoredScroll();
}

onMounted(() => {
  loadForRoute(kindFromRoute(route.name), String(route.params.collection));
});

onBeforeRouteUpdate((to) => {
  loadForRoute(kindFromRoute(to.name), String(to.params.collection));
});

watch(
  () => [route.name, route.params.collection] as const,
  ([name, id]) => {
    if (id == null) return;
    loadForRoute(kindFromRoute(name), String(id));
  },
);

// ── Download ────────────────────────────────────────────────────
// Whole-collection download by id — the server resolves the current
// member list and streams one zip, so nothing depends on how many
// pages the gallery has loaded (issue #3659).
function onDownload() {
  const c = currentCollection.value;
  if (!c || !c.rom_count) return;
  void romApi.downloadCollectionRoms({
    collectionId: c.id,
    kind: currentKind.value,
  });
  snackbar.info(t("gallery.selection-download-many", { n: c.rom_count }));
}

// ── Delete ──────────────────────────────────────────────────────
// Mirrors the Platform.vue admin flow: confirm dialog with
// `requireTyped` on the collection name, then API call → store remove
// → snackbar → navigate back to the index. Triggered from
// `CollectionSettingsTab`'s danger zone.
async function onDelete() {
  const c = currentCollection.value;
  if (!c || !editableKind.value) return;
  const ok = await confirm({
    title: t("collection.delete-collection", "Delete collection"),
    body: `This removes "${c.name}" (${c.rom_count} ROMs in the collection). The ROM files themselves are not deleted.`,
    confirmText: t("collection.delete-collection", "Delete collection"),
    tone: "danger",
    requireTyped: c.name,
  });
  if (!ok) return;

  deleting.value = true;
  try {
    if (editableKind.value === "smart") {
      await collectionApi.deleteSmartCollection((c as SmartCollection).id);
      collectionsStore.removeSmartCollection(c as SmartCollection);
    } else {
      await collectionApi.deleteCollection({ collection: c as Collection });
      collectionsStore.removeCollection(c as Collection);
    }
    snackbar.success(`Collection "${c.name}" deleted`, {
      icon: "mdi-check-bold",
    });
    router.push({ name: ROUTES.COLLECTIONS_INDEX });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string; detail?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to delete collection: ${
        e?.response?.data?.msg ||
        e?.response?.data?.detail ||
        e?.message ||
        "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <!-- LIBRARY — full GalleryShell with CollectionHead in #header so
       the head band scrolls naturally with the cards and the toolbar
       pins below it. -->
  <GalleryShell
    v-if="tab === 'library'"
    ref="shellRef"
    :has-header="!!currentCollection"
    :search-placeholder="t('collection.search-collection')"
    :empty-message="t('collection.empty')"
    :not-found="notFound"
    :not-found-message="t('collection.not-found')"
    :skeleton-row-count="4"
  >
    <template #header>
      <CollectionHead
        v-if="currentCollection"
        :collection="currentCollection"
        :kind="currentKind"
        :kind-label="kindLabel"
        :description="description"
        :covers="mosaicCovers"
        :tab="tab"
        :tabs="tabs"
        :can-download="canDownload"
        @update:tab="onTabChange"
        @download="onDownload"
      />
    </template>
  </GalleryShell>

  <!-- SETTINGS — plain scroll wrapper hosting the same CollectionHead
       above the tab body. Whole page scrolls together. -->
  <section v-else class="r-v2-coll-tabs">
    <div class="r-v2-coll-tabs__scroll">
      <CollectionHead
        v-if="currentCollection"
        :collection="currentCollection"
        :kind="currentKind"
        :kind-label="kindLabel"
        :description="description"
        :covers="mosaicCovers"
        :tab="tab"
        :tabs="tabs"
        :can-download="canDownload"
        @update:tab="onTabChange"
        @download="onDownload"
      />
      <RDivider class="r-v2-coll-tabs__divider" />
      <div
        v-if="editableKind && editableCollection"
        class="r-v2-coll-tabs__panel"
      >
        <CollectionSettingsTab
          :kind="editableKind"
          :collection="editableCollection"
          :deleting="deleting"
          @saved="onSaved"
          @delete="onDelete"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Settings branch — single scroll wrapper that owns the page scroll.
   The CollectionHead and the tab body scroll together as one surface,
   matching the platform-view layout. */
.r-v2-coll-tabs {
  /* `dvh` (not `vh`) so the section matches the mobile visible viewport
     instead of the larger address-bar-hidden one — otherwise it spills below
     the fold and stacks a second, document-level scroll on the internal one
     ("double scroll"). Same rationale as GalleryShell / IndexShell. */
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  overflow: hidden;
  position: relative;
}
/* On sm-and-down the layout <main> reserves the bottom tab bar's height; this
   full-height section would otherwise sit on top of that padding and push the
   document past one viewport. Cancel it with a matching negative margin so the
   section extends under the (translucent) bar with a single scroll — the inner
   scroll's bottom spacer lifts the last content (danger zone) clear of it. */
html[data-bp~="sm-and-down"] .r-v2-coll-tabs {
  margin-bottom: calc(
    -1 * (var(--r-bottom-nav-h) + env(safe-area-inset-bottom))
  );
}

.r-v2-coll-tabs__scroll {
  height: 100%;
  overflow-y: auto;
  padding: 32px var(--r-row-pad) 60px;
}
html[data-bp~="sm-and-down"] .r-v2-coll-tabs__scroll {
  padding-bottom: calc(
    var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px
  );
}

.r-v2-coll-tabs__divider {
  margin: 0 0 24px;
}

.r-v2-coll-tabs__panel {
  min-height: 0;
}
</style>
