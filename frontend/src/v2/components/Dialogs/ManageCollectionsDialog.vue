<script setup lang="ts">
// ManageCollectionsDialog — collection picker that matches the mockup's
// menu-panel shape. Driven by the `showManageCollectionsDialog` emitter.
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
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import collectionApi from "@/services/api/collection";
import storeCollections, {
  type Collection,
  type CollectionType,
} from "@/stores/collections";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import CollectionPickerRow from "@/v2/components/Collections/CollectionPickerRow.vue";
import NewCollectionRow from "@/v2/components/Collections/NewCollectionRow.vue";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import { collectionCoverList } from "@/v2/utils/collectionCovers";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const show = ref(false);
const collectionsStore = storeCollections();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const { toWebp } = useWebpSupport();

function coversFor(collection: CollectionType): string[] {
  return collectionCoverList(collection, toWebp);
}

const roms = ref<SimpleRom[]>([]);

const pendingCollections = ref(new Set<number>());
// Optimistic state is now tri-state (off | some | all). When the user
// clicks a row we paint the *resolved* next state immediately and
// reconcile when the API responds — `undefined` means "fall back to
// the collection's actual membership computed against `roms.value`".
const optimistic = ref(new Map<number, "off" | "some" | "all">());

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
emitter?.on("showManageCollectionsDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showManageCollectionsDialog", openHandler));

// Notify any GameActionBtn that opened us so it can drop its pinned-hover
// state — covers every close path (X, scrim, Escape, programmatic close).
watch(show, (open) => {
  if (!open) emitter?.emit("closeManageCollectionsDialog", null);
});

/** Resolve a collection's membership against the open dialog's
 *  selection. "all" when every selected rom is in the collection,
 *  "some" when at least one (but not all) is, "off" otherwise. The
 *  "some" state only appears for bulk dialogs — a single-rom dialog
 *  collapses to off / all. */
function membershipState(collection: Collection): "off" | "some" | "all" {
  const override = optimistic.value.get(collection.id);
  if (override !== undefined) return override;
  if (roms.value.length === 0) return "off";
  const ids = collection.rom_ids ?? [];
  const idSet = new Set(ids);
  let inCount = 0;
  for (const rom of roms.value) {
    if (idSet.has(rom.id)) inCount += 1;
  }
  if (inCount === 0) return "off";
  if (inCount === roms.value.length) return "all";
  return "some";
}

async function toggle(collection: Collection) {
  if (pendingCollections.value.has(collection.id)) return;
  const prevState = membershipState(collection);
  // Cycle policy mirrors typical file-manager tri-state checkboxes:
  //   off  → all  (add every selected rom to the collection)
  //   some → all  (add the missing ones, no removals)
  //   all  → off  (remove every selected rom from the collection)
  const nextState: "off" | "all" = prevState === "all" ? "off" : "all";
  const adding = nextState === "all";

  optimistic.value.set(collection.id, nextState);
  pendingCollections.value.add(collection.id);

  // For the "some → all" transition we still issue an add against all
  // selected ids — the backend de-dupes against existing membership,
  // so this is safe and saves a per-id diff round-trip from the
  // frontend.
  const romIds = roms.value.map((r) => r.id);
  try {
    const { data } = adding
      ? await collectionApi.addRomsToCollection(collection.id, romIds)
      : await collectionApi.removeRomsFromCollection(collection.id, romIds);
    collectionsStore.updateCollection(data);
    optimistic.value.delete(collection.id);
  } catch (error: unknown) {
    optimistic.value.set(collection.id, prevState);
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(
      axiosErr.response?.data?.detail ??
        (adding
          ? t("rom.collection-add-failed")
          : t("rom.collection-remove-failed")),
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
    snackbar.error(t("collection.name-exists"), { icon: "mdi-close-circle" });
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
      axiosErr.response?.data?.detail ?? t("collection.create-failed"),
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
    return t("rom.selection-count", { n: roms.value.length });
  }
  return "";
});

const ownedCollections = computed(() => collectionsStore.ownedCollections);

// Header cover thumbnail — single-rom invocations get the game's cover
// alongside the title (same `<GameCard size="xs" decorative>` shape
// the list-mode row uses, so the header reads as a sibling of the
// gallery surface). Bulk invocations stay text-only since one cover
// can't represent the selection.
const singleRom = computed(() =>
  roms.value.length === 1 ? roms.value[0] : null,
);

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
  <RDialog
    v-model="show"
    :width="mdAndUp ? 440 : '95vw'"
    class="r-v2-mng-coll-dialog"
    @close="closeDialog"
  >
    <!-- Two-line title block replaces the single-line default so the
         bold "Manage collections" + muted game subtitle stack. Close X
         is provided by RDialog in its own header chrome. -->
    <template #header>
      <div class="r-v2-mng-coll__head">
        <GameCard
          v-if="singleRom"
          class="r-v2-mng-coll__head-cover"
          :rom="singleRom"
          size="xs"
          decorative
          :show-title="false"
          :show-platform-icon="false"
        />
        <div class="r-v2-mng-coll__head-text">
          <span class="r-v2-mng-coll__head-title">
            {{ t("rom.manage-collections") }}
          </span>
          <span v-if="subtitle" class="r-v2-mng-coll__head-subtitle">
            {{ subtitle }}
          </span>
        </div>
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

      <RDivider v-if="ownedCollections.length > 0" full-width />

      <!-- Existing collection rows — instant toggle, no commit step. -->
      <ul v-if="ownedCollections.length" class="r-v2-mng-coll__list">
        <li v-for="collection in ownedCollections" :key="collection.id">
          <CollectionPickerRow
            :name="collection.name"
            :count="collection.rom_count"
            :covers="coversFor(collection)"
            :state="membershipState(collection)"
            :busy="pendingCollections.has(collection.id)"
            :tile-size="46"
            @toggle="toggle(collection)"
          />
        </li>
      </ul>

      <div v-else class="r-v2-mng-coll__empty">
        {{ t("collection.no-collections-yet-hint") }}
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
/* Header — optional GameCard thumbnail + stacked title (14px bold) +
   subtitle (11.5px muted) inside RDialog's single header slot. */
.r-v2-mng-coll__head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.r-v2-mng-coll__head-cover {
  flex-shrink: 0;
}
.r-v2-mng-coll__head-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.r-v2-mng-coll__head-title {
  font-size: 14px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-overlay-fg);
  letter-spacing: -0.005em;
  line-height: 1.25;
}
.r-v2-mng-coll__head-subtitle {
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-regular);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

/* Row list — sits flush against the dialog edges. This dialog drops
   the standard RDialog body padding (see the `:deep(.r-dialog__body)`
   override below) so rows read as menu items, not as padded cards. */
.r-v2-mng-coll__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 360px;
  overflow-y: auto;
}

.r-v2-mng-coll__empty {
  padding: 24px 16px;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  text-align: center;
}
</style>

<!-- Unscoped overrides — `.r-dialog__body` is rendered (and teleported)
     by RDialog with its own data-v hash, so a scoped `:deep()` rule
     from this component doesn't actually land on it. The unscoped
     selector targets the body via a class we attach to RDialog's root
     overlay (flows through `v-bind="$attrs"`), keeping the override
     localised to this dialog. -->
<style>
.r-v2-mng-coll-dialog .r-dialog__body {
  padding: 0;
  gap: 0;
}
</style>
