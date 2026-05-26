<script setup lang="ts">
// Collection gallery — thin orchestrator around `GalleryShell`. Owns
// the regular/virtual/smart collection load flow and fills the shell's
// `#header` slot with a CollectionMosaic-fronted InfoPanel. A kebab
// menu in the `#actions` slot opens the unified
// `CollectionSettingsDrawer` (regular / smart only — virtual
// collections are computed and have no editable fields).
import { RBtn, RChip, RDivider, RMenu, RMenuItem } from "@v2/lib";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import storeCollections, {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import CollectionSettingsDrawer from "@/v2/components/Gallery/CollectionSettingsDrawer.vue";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import Stat from "@/v2/components/shared/Stat.vue";
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
const settingsOpen = ref(false);
const deleting = ref(false);

// Virtual collections are computed (no editable fields) — only
// regular / smart get the settings entry-point.
const editableKind = computed<"regular" | "smart" | null>(() => {
  if (currentKind.value === "regular") return "regular";
  if (currentKind.value === "smart") return "smart";
  return null;
});

// Ownership gate for showing the kebab. v1 only renders the drawer's
// edit/delete affordances for owners with `collections.write` — if the
// user can do neither, hide the kebab entirely to avoid a dead menu.
const isOwner = computed(() => {
  const c = currentCollection.value as { user_id?: number | null } | null;
  return !!c && c.user_id != null && c.user_id === auth.user?.id;
});
const showKebab = computed(
  () =>
    !!editableKind.value &&
    isOwner.value &&
    auth.scopes.includes("collections.write"),
);

function onSaved(updated: Collection | SmartCollection) {
  currentCollection.value = updated;
}

// Narrowed view of `currentCollection` for the settings drawer —
// `editableKind` guarantees we're not in the virtual branch, so we
// can hand the drawer a `Collection | SmartCollection` reference
// without a per-template cast (the template parser misreads the
// union pipe as a deprecated Vue filter).
const editableCollection = computed<Collection | SmartCollection | null>(() =>
  editableKind.value
    ? (currentCollection.value as Collection | SmartCollection)
    : null,
);

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

// ── Delete ──────────────────────────────────────────────────────
// Mirrors the Platform.vue admin-kebab pattern: confirm dialog with
// `requireTyped` on the collection name, then API call → store
// remove → snackbar → navigate back to the index. Lives at the view
// level (not in the settings drawer) so the destructive affordance
// sits alongside Settings in the kebab menu — same vocabulary the
// user sees on every other gallery surface.
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
    settingsOpen.value = false;
    router.push({ name: "collections" });
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

        <template v-if="showKebab" #actions>
          <RMenu location="bottom end" :offset="6" width="220px">
            <template #activator="{ props: activatorProps }">
              <RBtn
                v-bind="activatorProps"
                variant="outlined"
                surface
                icon="mdi-dots-vertical"
                rounded="circle"
                aria-label="Collection actions"
              />
            </template>
            <RMenuItem
              :label="t('collection.settings', 'Settings…')"
              icon="mdi-cog-outline"
              @click="settingsOpen = true"
            />
            <RDivider />
            <RMenuItem
              :label="t('collection.delete-collection', 'Delete collection')"
              icon="mdi-delete-outline"
              variant="danger"
              :disabled="deleting"
              @click="onDelete"
            />
          </RMenu>
        </template>
      </InfoPanel>
    </template>
  </GalleryShell>

  <CollectionSettingsDrawer
    v-if="editableKind && editableCollection"
    v-model="settingsOpen"
    :kind="editableKind"
    :collection="editableCollection"
    @saved="onSaved"
  />
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
