<script setup lang="ts">
// AddRomsToCollectionDialog — collection picker that matches the mockup's
// menu-panel shape. Driven by the `showAddToCollectionDialog` emitter.
//
// Uses the v2 RDialog primitive — RDialog was updated to share the
// RMenuPanel visual language (14px radius, deep glass, menu-style shadow)
// so this picker reads as a sibling of the user menu / ROM context menu.
// No direct VDialog here; every v2 dialog flows through the primitive.
//
// Shape (top → bottom):
//   * Bold "Manage collections" title + muted game subtitle in the
//     header slot (single `div` inside #header; close X is provided by
//     RDialog).
//   * "New Collection" CTA row. Collapsed: brand-tinted + tile +
//     "New Collection" label. Click expands to an inline Create /
//     Cancel input.
//   * Divider.
//   * List of owned collections — avatar, name, count, brand-primary
//     circular tick when on. Clicking toggles INSTANTLY (optimistic
//     update + API call; reverts on failure).
//   * Empty state if no collections exist.
import { RDialog, RDivider } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import collectionApi from "@/services/api/collection";
import storeCollections, {
  type Collection,
  type CollectionType,
} from "@/stores/collections";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import CollectionPickerRow from "@/v2/components/Collections/CollectionPickerRow.vue";
import NewCollectionRow from "@/v2/components/Collections/NewCollectionRow.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const collectionsStore = storeCollections();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const { toWebp } = useWebpSupport();

// Mirrors CollectionsIndex.coversFor — prefers the multi-cover array,
// falls back to the single cover when that's all we have so a regular
// collection's one custom cover still renders. Webp-swapped when the
// backend supports it.
function coversFor(collection: CollectionType): string[] {
  const multi =
    (collection as { path_covers_small?: string[] }).path_covers_small ?? [];
  const single = collection.path_cover_small ?? null;
  const list = multi.length ? multi.slice(0, 4) : single ? [single] : [];
  return list.map(toWebp);
}

const roms = ref<SimpleRom[]>([]);

const pendingCollections = ref(new Set<number>());
const optimistic = ref(new Map<number, boolean>());

const creating = ref(false);
const createExpanded = ref(false);
const newName = ref("");

const openHandler = (romsToAdd: SimpleRom[]) => {
  roms.value = romsToAdd;
  optimistic.value = new Map();
  pendingCollections.value = new Set();
  newName.value = "";
  createExpanded.value = false;
  show.value = true;
};
emitter?.on("showAddToCollectionDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showAddToCollectionDialog", openHandler));

function allIn(collection: Collection): boolean {
  const ids = collection.rom_ids ?? [];
  return roms.value.length > 0 && roms.value.every((r) => ids.includes(r.id));
}

function isChecked(collection: Collection): boolean {
  const override = optimistic.value.get(collection.id);
  if (override !== undefined) return override;
  return allIn(collection);
}

async function toggle(collection: Collection) {
  if (pendingCollections.value.has(collection.id)) return;
  const wasChecked = isChecked(collection);
  const nextChecked = !wasChecked;

  optimistic.value.set(collection.id, nextChecked);
  pendingCollections.value.add(collection.id);

  const romIds = roms.value.map((r) => r.id);
  try {
    const { data } = nextChecked
      ? await collectionApi.addRomsToCollection(collection.id, romIds)
      : await collectionApi.removeRomsFromCollection(collection.id, romIds);
    collectionsStore.updateCollection(data);
    optimistic.value.delete(collection.id);
  } catch (error: unknown) {
    optimistic.value.set(collection.id, wasChecked);
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(
      axiosErr.response?.data?.detail ??
        (nextChecked
          ? t("rom.collection-add-failed", "Couldn't add to collection")
          : t(
              "rom.collection-remove-failed",
              "Couldn't remove from collection",
            )),
      { icon: "mdi-close-circle" },
    );
  } finally {
    pendingCollections.value.delete(collection.id);
  }
}

async function createNewCollection() {
  const name = newName.value.trim();
  if (!name || creating.value) return;
  if (collectionsStore.ownedCollections.some((c) => c.name === name)) {
    snackbar.error(
      t(
        "collection.name-exists",
        `A collection called "${name}" already exists.`,
      ),
      { icon: "mdi-close-circle" },
    );
    return;
  }
  creating.value = true;
  try {
    const created = await collectionApi.createCollection({
      collection: { name },
    });
    collectionsStore.addCollection(created);
    void toggle(created);
    newName.value = "";
    createExpanded.value = false;
  } catch (error: unknown) {
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(
      axiosErr.response?.data?.detail ?? "Failed to create collection",
      { icon: "mdi-close-circle" },
    );
  } finally {
    creating.value = false;
  }
}

function cancelCreate() {
  newName.value = "";
  createExpanded.value = false;
}

const subtitle = computed(() => {
  if (roms.value.length === 1) {
    return roms.value[0].name ?? roms.value[0].fs_name ?? "";
  }
  if (roms.value.length > 1) {
    return t("rom.selection-count", `${roms.value.length} games`);
  }
  return "";
});

const ownedCollections = computed(() => collectionsStore.ownedCollections);

function closeDialog() {
  roms.value = [];
  optimistic.value = new Map();
  pendingCollections.value = new Set();
  newName.value = "";
  createExpanded.value = false;
  show.value = false;
}
</script>

<template>
  <RDialog v-model="show" :width="mdAndUp ? 440 : '95vw'" @close="closeDialog">
    <!-- Two-line title block replaces the single-line default so the
         bold "Manage collections" + muted game subtitle stack. Close X
         is provided by RDialog in its own header chrome. -->
    <template #header>
      <div class="r-v2-pick-coll__head">
        <span class="r-v2-pick-coll__head-title">
          {{ t("rom.manage-collections", "Manage collections") }}
        </span>
        <span v-if="subtitle" class="r-v2-pick-coll__head-subtitle">
          {{ subtitle }}
        </span>
      </div>
    </template>

    <template #content>
      <NewCollectionRow
        v-model:expanded="createExpanded"
        v-model:name="newName"
        :creating="creating"
        :tile-size="46"
        @create="createNewCollection"
        @cancel="cancelCreate"
      />

      <RDivider v-if="ownedCollections.length > 0" />

      <!-- Existing collection rows — instant toggle, no commit step. -->
      <ul v-if="ownedCollections.length" class="r-v2-pick-coll__list">
        <li v-for="collection in ownedCollections" :key="collection.id">
          <CollectionPickerRow
            :name="collection.name"
            :count="collection.rom_count"
            :covers="coversFor(collection)"
            :checked="isChecked(collection)"
            :busy="pendingCollections.has(collection.id)"
            :tile-size="46"
            @toggle="toggle(collection)"
          />
        </li>
      </ul>

      <div v-else class="r-v2-pick-coll__empty">
        {{
          t(
            "collection.no-collections-yet",
            "No collections yet. Create one above.",
          )
        }}
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
/* Header typography — stacked title (14px bold) + subtitle (11.5px
   muted) inside RDialog's single header slot. */
.r-v2-pick-coll__head {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.r-v2-pick-coll__head-title {
  font-size: 14px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-overlay-fg);
  letter-spacing: -0.005em;
  line-height: 1.25;
}
.r-v2-pick-coll__head-subtitle {
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-regular);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

/* Row list — edge-to-edge against RDialog's body padding so each row
   reads like a menu item rather than a padded card. */
.r-v2-pick-coll__list {
  list-style: none;
  margin: 0 0 0 -18px;
  padding: 0px;
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 360px;
  overflow-y: auto;
}

.r-v2-pick-coll__empty {
  padding: 24px 16px;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  text-align: center;
}
</style>
