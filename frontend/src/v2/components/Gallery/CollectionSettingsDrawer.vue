<script setup lang="ts">
// CollectionSettingsDrawer — right-anchored RDrawer that replaces v1's
// `CollectionInfoDrawer` (regular collections) and
// `SmartCollectionInfoDrawer` (smart collections). One component, two
// branches:
//
//   * regular → name / description / public, cover artwork
//     (SteamGridDB search · file upload · remove), filter_criteria not
//     applicable.
//   * smart   → name / description / public, filter_criteria displayed
//     read-only (matches v1 — editing the criteria isn't surfaced in
//     the drawer).
//
// Virtual collections never open this drawer — they're computed and
// have no editable fields.
//
// Delete lives in `Collection.vue`'s kebab menu (mirroring the Platform
// admin pattern), not here — the drawer is purely "edit this".
//
// Cover artwork flow:
//   • Search → emits `showSearchCoverDialog` (global SearchCoverDialog
//     handles it). On selection it emits `updateUrlCover` which we
//     hear while the drawer is open and stash as the pending
//     `url_cover` (the preview swaps to the SGDB grid URL).
//   • Upload → native file picker, FileReader for preview, sets
//     `pendingArtwork` (File).
//   • Remove → marks `removeCover = true`, preview drops to the
//     placeholder mosaic.
//   • Save → PUT /collections/:id with `artwork` and/or `url_cover` and
//     `remove_cover` flag; on success patches the local store.
import { RBtn, RChip, RIcon, RSwitch, RTag, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import collectionApi, {
  type UpdatedCollection,
} from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import storeCollections, {
  type Collection,
  type SmartCollection,
} from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import RDrawer from "@/v2/lib/overlays/RDrawer/RDrawer.vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import {
  summarizeSmartFilterCriteria,
  type SmartFilterCriteria,
} from "@/v2/utils/smartCollectionCriteria";

defineOptions({ inheritAttrs: false });

type Kind = "regular" | "smart";

const props = defineProps<{
  modelValue: boolean;
  kind: Kind;
  collection: Collection | SmartCollection;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "saved", c: Collection | SmartCollection): void;
}>();

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const auth = storeAuth();
const collectionsStore = storeCollections();
const galleryRoms = storeGalleryRoms();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const { toWebp } = useWebpSupport();

// ── Edit form state ─────────────────────────────────────────────
// Mirror v1: name, description, is_public are editable. Pending cover
// changes live in `pendingArtwork` (uploaded file) + `pendingUrlCover`
// (SteamGridDB URL) + `removeCover` (flag). Only one of artwork /
// pendingUrlCover applies on save.
const form = ref({
  name: "",
  description: "",
  isPublic: false,
});
const pendingArtwork = ref<File | null>(null);
const pendingUrlCover = ref<string | null>(null);
const previewDataUrl = ref<string | null>(null);
const removeCover = ref(false);
const saving = ref(false);

// Hidden file input — clicked programmatically by the "Upload" action.
const fileInputRef = ref<HTMLInputElement | null>(null);

// Ownership / permission gate. Both v1 drawers gate edit / delete on
// `user_id === auth.user.id && scopes.includes("collections.write")`.
// v2 uses the same heuristic since `useCan('collection.edit')` isn't
// yet scoped per-collection.
const isOwner = computed(() => {
  const c = props.collection as { user_id?: number | null };
  return c.user_id != null && c.user_id === auth.user?.id;
});
const canEdit = computed(
  () => isOwner.value && auth.scopes.includes("collections.write"),
);

const dirty = computed(() => {
  const c = props.collection;
  return (
    form.value.name !== c.name ||
    (form.value.description ?? "") !== (c.description ?? "") ||
    form.value.isPublic !== c.is_public ||
    !!pendingArtwork.value ||
    !!pendingUrlCover.value ||
    removeCover.value
  );
});

// Reset the form every time the drawer opens. We don't clear on close
// in case the user re-opens before navigating — but on `open` flip we
// always re-snapshot from the live collection so concurrent backend
// updates surface.
watch(
  () => props.modelValue,
  (open) => {
    if (open) snapshot();
  },
  { immediate: true },
);

// External listener: SearchCoverDialog emits `updateUrlCover` with the
// chosen URL. We adopt it as the pending cover and let the user keep
// editing other fields before saving. Only honour the event while we
// own focus (open) so EditRomDialog's listener isn't trampled.
const onUrlCover = (url: string) => {
  if (!props.modelValue) return;
  pendingUrlCover.value = url;
  pendingArtwork.value = null;
  previewDataUrl.value = url;
  removeCover.value = false;
};
watch(
  () => props.modelValue,
  (open) => {
    if (open) emitter?.on("updateUrlCover", onUrlCover);
    else emitter?.off("updateUrlCover", onUrlCover);
  },
);

function snapshot() {
  const c = props.collection;
  form.value = {
    name: c.name,
    description: c.description ?? "",
    isPublic: c.is_public ?? false,
  };
  pendingArtwork.value = null;
  pendingUrlCover.value = null;
  previewDataUrl.value = null;
  removeCover.value = false;
}

// ── Cover preview ───────────────────────────────────────────────
// Pick the right source: pending (user just picked something) → local
// preview → existing artwork → mosaic fallback.
const coverSrc = computed<string | null>(() => {
  if (removeCover.value) return null;
  if (previewDataUrl.value) return previewDataUrl.value;
  if (pendingUrlCover.value) return pendingUrlCover.value;
  const c = props.collection as { path_cover_small?: string | null };
  return c.path_cover_small ? toWebp(c.path_cover_small) : null;
});
const mosaicFallback = computed<string[]>(() => {
  const c = props.collection as { path_covers_small?: string[] };
  return (c.path_covers_small ?? []).slice(0, 4).map(toWebp);
});

// Smart-collection filter criteria — read-only display. The summary
// helper translates the raw JSON into a structured list of rows the
// drawer renders as labelled chip groups (one section per criterion).
// Shared with CreateSmartCollectionDialog so the preview during
// creation matches what shows up here afterwards.
function platformLookup(id: number): string | null {
  return allPlatforms.value.find((p) => p.id === id)?.display_name ?? null;
}
function collectionLookup(id: number): string | null {
  return collectionsStore.getCollection(id)?.name ?? null;
}
function virtualCollectionLookup(id: string): string | null {
  return collectionsStore.getVirtualCollection(id)?.name ?? null;
}
function smartCollectionLookup(id: number): string | null {
  return collectionsStore.getSmartCollection(id)?.name ?? null;
}
const filterSummary = computed(() => {
  if (props.kind !== "smart") return [];
  const c = props.collection as SmartCollection;
  const fc = (c.filter_criteria ?? {}) as SmartFilterCriteria;
  return summarizeSmartFilterCriteria(fc, t, {
    platform: platformLookup,
    collection: collectionLookup,
    virtualCollection: virtualCollectionLookup,
    smartCollection: smartCollectionLookup,
  });
});

// ── Cover actions ───────────────────────────────────────────────
function openSearchCover() {
  emitter?.emit("showSearchCoverDialog", {
    term: props.collection.name,
  });
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

function onFilePicked(evt: Event) {
  const input = evt.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  pendingArtwork.value = file;
  pendingUrlCover.value = null;
  removeCover.value = false;

  const reader = new FileReader();
  reader.onload = () => {
    previewDataUrl.value = reader.result?.toString() ?? null;
  };
  reader.readAsDataURL(file);

  // Reset the input so re-picking the same file fires `change` again.
  input.value = "";
}

function clearArtwork() {
  pendingArtwork.value = null;
  pendingUrlCover.value = null;
  previewDataUrl.value = null;
  removeCover.value = true;
}

// ── Save ────────────────────────────────────────────────────────
async function save() {
  if (!dirty.value || saving.value || !canEdit.value) return;
  saving.value = true;
  try {
    if (props.kind === "smart") {
      const payload: SmartCollection = {
        ...(props.collection as SmartCollection),
        name: form.value.name.trim(),
        description: form.value.description,
        is_public: form.value.isPublic,
      };
      const { data } = await collectionApi.updateSmartCollection({
        smartCollection: payload,
      });
      collectionsStore.updateSmartCollection(data);
      if (galleryRoms.currentSmartCollection?.id === data.id) {
        galleryRoms.setCurrentSmartCollection(data);
      }
      emit("saved", data);
    } else {
      const payload: UpdatedCollection = {
        ...(props.collection as Collection),
        name: form.value.name.trim(),
        description: form.value.description,
        is_public: form.value.isPublic,
        artwork: pendingArtwork.value ?? undefined,
        url_cover: pendingUrlCover.value,
      };
      const { data } = await collectionApi.updateCollection({
        collection: payload,
        removeCover: removeCover.value,
      });
      collectionsStore.updateCollection(data);
      if (galleryRoms.currentCollection?.id === data.id) {
        galleryRoms.setCurrentCollection(data);
      }
      emit("saved", data);
    }
    snackbar.success(t("collection.updated", "Collection updated"), {
      icon: "mdi-check-bold",
    });
    snapshot();
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string; detail?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to update collection: ${
        e?.response?.data?.msg ||
        e?.response?.data?.detail ||
        e?.message ||
        "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    saving.value = false;
  }
}

function discard() {
  snapshot();
}
</script>

<template>
  <RDrawer
    :model-value="modelValue"
    :width="460"
    icon="mdi-cog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <span>{{ collection.name }}</span>
    </template>

    <!-- Cover artwork — regular collections only. Smart collections
         derive their cover from the contained ROMs at runtime, so
         giving the user an upload UI here would be misleading. -->
    <section v-if="kind === 'regular'" class="r-v2-coll-set__section">
      <header class="r-v2-coll-set__section-head">
        <RIcon icon="mdi-image-outline" size="14" />
        <span>{{ t("collection.cover", "Cover artwork") }}</span>
      </header>
      <div class="r-v2-coll-set__cover">
        <div class="r-v2-coll-set__cover-preview">
          <img
            v-if="coverSrc"
            :src="coverSrc"
            :alt="collection.name"
            class="r-v2-coll-set__cover-img"
          />
          <CollectionMosaic
            v-else
            :covers="mosaicFallback"
            aspect-ratio="140 / 188"
          />
        </div>
        <div v-if="canEdit" class="r-v2-coll-set__cover-actions">
          <RBtn
            icon="mdi-image-search-outline"
            variant="outlined"
            density="compact"
            :tooltip="t('rom.search-cover', 'Search cover')"
            @click="openSearchCover"
          />
          <RBtn
            icon="mdi-pencil"
            variant="outlined"
            density="compact"
            :tooltip="t('rom.upload-cover', 'Upload cover')"
            @click="triggerFileInput"
          />
          <RBtn
            icon="mdi-delete"
            variant="outlined"
            density="compact"
            color="danger"
            :tooltip="t('common.remove', 'Remove')"
            @click="clearArtwork"
          />
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            class="r-v2-coll-set__file"
            :aria-label="t('rom.upload-cover', 'Upload cover')"
            @change="onFilePicked"
          />
        </div>
      </div>
    </section>

    <!-- Details (edit form) — both kinds. -->
    <section class="r-v2-coll-set__section">
      <header class="r-v2-coll-set__section-head">
        <RIcon icon="mdi-pencil-outline" size="14" />
        <span>{{ t("common.details", "Details") }}</span>
      </header>
      <div class="r-v2-coll-set__form">
        <RTextField
          v-model="form.name"
          :placeholder="t('collection.name', 'Name')"
          prefix-label="stacked"
          :disabled="!canEdit"
          required
          hide-details
        >
          <template #prefix-label>{{ t("collection.name", "Name") }}</template>
        </RTextField>
        <RTextField
          v-model="form.description"
          :placeholder="t('collection.description', 'Description')"
          prefix-label="stacked"
          :disabled="!canEdit"
          multiline
          :rows="3"
          hide-details
        >
          <template #prefix-label>
            {{ t("collection.description", "Description") }}
          </template>
        </RTextField>
        <div class="r-v2-coll-set__row">
          <RSwitch
            v-model="form.isPublic"
            :disabled="!canEdit"
            :label="
              form.isPublic
                ? t('collection.public', 'Public')
                : t('collection.private', 'Private')
            "
          />
        </div>
      </div>
    </section>

    <!-- Smart collection: filter criteria (read-only). One row per
         criterion: icon + label (+ AND/OR/NONE tag for multi-select
         groups) and the values as chips below. Matches the create-
         dialog preview shape so users see the same vocabulary in both
         places. -->
    <section
      v-if="kind === 'smart' && filterSummary.length > 0"
      class="r-v2-coll-set__section"
    >
      <header class="r-v2-coll-set__section-head">
        <RIcon icon="mdi-filter-variant" size="14" />
        <span>{{ t("collection.filters", "Filters") }}</span>
      </header>
      <ul class="r-v2-coll-set__filters">
        <li
          v-for="row in filterSummary"
          :key="row.key"
          class="r-v2-coll-set__filter-row"
        >
          <span class="r-v2-coll-set__filter-label">
            <RIcon :icon="row.icon" size="14" />
            <span>{{ row.label }}</span>
            <RTag
              v-if="row.logic"
              tone="brand"
              size="x-small"
              class="r-v2-coll-set__filter-logic"
            >
              {{ row.logic }}
            </RTag>
          </span>
          <div v-if="row.values?.length" class="r-v2-coll-set__filter-values">
            <RChip
              v-for="(v, i) in row.values"
              :key="`${row.key}-${i}`"
              size="x-small"
              variant="translucent"
            >
              {{ v }}
            </RChip>
          </div>
        </li>
      </ul>
    </section>

    <template v-if="canEdit" #footer>
      <RBtn variant="text" :disabled="!dirty || saving" @click="discard">
        {{ t("common.discard", "Discard") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :disabled="!dirty || !form.name.trim()"
        :loading="saving"
        @click="save"
      >
        {{ t("common.apply", "Apply") }}
      </RBtn>
    </template>
  </RDrawer>
</template>

<style scoped>
.r-v2-coll-set__section {
  margin-bottom: 20px;
}
.r-v2-coll-set__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

/* ── Cover ──────────────────────────────────────────────────────── */
/* Same shape as `EditRomDialog.r-v2-edit__cover-col`: a centred column
   with the cover thumb stacked over a row of icon-only action buttons.
   Keeps both surfaces (edit ROM + collection settings) visually aligned. */
.r-v2-coll-set__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-coll-set__cover-preview {
  width: 140px;
  height: 188px;
  flex-shrink: 0;
  border-radius: var(--r-radius-md);
  border: 1px solid var(--r-color-border-strong);
  overflow: hidden;
  background: var(--r-color-surface);
}
.r-v2-coll-set__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.r-v2-coll-set__cover-actions {
  display: flex;
  gap: 4px;
}
.r-v2-coll-set__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

/* ── Form ───────────────────────────────────────────────────────── */
.r-v2-coll-set__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-v2-coll-set__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Filters (smart) ────────────────────────────────────────────── */
.r-v2-coll-set__filters {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-coll-set__filter-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-coll-set__filter-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-coll-set__filter-logic {
  margin-left: 4px;
  text-transform: uppercase;
}
.r-v2-coll-set__filter-values {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 20px;
}
</style>
