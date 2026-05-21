<script setup lang="ts">
// CreateSmartCollectionDialog — captures the current galleryFilter state
// as a smart collection. v2 replacement for v1's
// `components/common/Collection/Dialog/CreateSmartCollection.vue`.
//
// Flow:
//   • Emitter fires `showCreateSmartCollectionDialog` (typically from
//     the FilterDrawer footer CTA).
//   • If no filters are active we refuse to open and surface a snackbar
//     hint — same guard v1 had, just routed through the v2 channel.
//   • The dialog snapshots `galleryFilter` once on open (so further
//     toggles in the gallery don't leak into the preview) and lets the
//     user name / describe / mark public.
//   • Submit → POST /collections/smart → store add → navigate to the
//     freshly-created smart collection.
//
// Serialization + summary live in `@/v2/utils/smartCollectionCriteria`
// so the read-only display inside CollectionSettingsDrawer renders from
// the same rules.
import {
  RBtn,
  RChip,
  RDialog,
  RForm,
  RIcon,
  RSwitch,
  RTextField,
  RTag,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import {
  buildSmartFilterCriteria,
  hasAnySmartFilterCriteria,
  summarizeSmartFilterCriteria,
  type SmartFilterCriteria,
} from "@/v2/utils/smartCollectionCriteria";
import { required } from "@/v2/utils/validation";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const router = useRouter();
const snackbar = useSnackbar();
const emitter = inject<Emitter<Events>>("emitter");

const galleryFilter = storeGalleryFilter();
const galleryRoms = storeGalleryRoms();
const collectionsStore = storeCollections();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);

const show = ref(false);
const submitting = ref(false);
const formValid = ref(true);
const name = ref("");
const description = ref("");
const isPublic = ref(false);

// Snapshot the criteria once when the dialog opens. We don't want the
// preview to keep updating as the user toggles filters in the gallery
// behind the dialog — what the user saw at the moment they clicked the
// CTA is what gets saved.
const snapshot = ref<SmartFilterCriteria>({});

const nameRules = [required(t("common.required", "Required"))];

const openHandler = () => {
  // v1 guarded with a snackbar warning here — keep that behaviour so
  // the user gets a hint instead of an empty preview.
  const next = buildSmartFilterCriteria(
    {
      searchTerm: galleryFilter.searchTerm,
      filterMatched: galleryFilter.filterMatched,
      filterFavorites: galleryFilter.filterFavorites,
      filterDuplicates: galleryFilter.filterDuplicates,
      filterPlayables: galleryFilter.filterPlayables,
      filterRA: galleryFilter.filterRA,
      filterMissing: galleryFilter.filterMissing,
      filterVerified: galleryFilter.filterVerified,
      selectedPlatforms: galleryFilter.selectedPlatforms,
      selectedGenres: galleryFilter.selectedGenres,
      genresLogic: galleryFilter.genresLogic,
      selectedFranchises: galleryFilter.selectedFranchises,
      franchisesLogic: galleryFilter.franchisesLogic,
      selectedCollections: galleryFilter.selectedCollections,
      collectionsLogic: galleryFilter.collectionsLogic,
      selectedCompanies: galleryFilter.selectedCompanies,
      companiesLogic: galleryFilter.companiesLogic,
      selectedAgeRatings: galleryFilter.selectedAgeRatings,
      ageRatingsLogic: galleryFilter.ageRatingsLogic,
      selectedRegions: galleryFilter.selectedRegions,
      regionsLogic: galleryFilter.regionsLogic,
      selectedLanguages: galleryFilter.selectedLanguages,
      languagesLogic: galleryFilter.languagesLogic,
      selectedPlayerCounts: galleryFilter.selectedPlayerCounts,
      playerCountsLogic: galleryFilter.playerCountsLogic,
      selectedStatuses: galleryFilter.selectedStatuses,
      statusesLogic: galleryFilter.statusesLogic,
    },
    galleryRoms.currentPlatform,
  );

  if (!hasAnySmartFilterCriteria(next)) {
    snackbar.warning(
      t(
        "collection.smart-no-filters",
        "Apply some filters before creating a smart collection.",
      ),
      { icon: "mdi-information" },
    );
    return;
  }

  snapshot.value = next;
  name.value = "";
  description.value = "";
  isPublic.value = false;
  show.value = true;
};
emitter?.on("showCreateSmartCollectionDialog", openHandler);
onBeforeUnmount(() =>
  emitter?.off("showCreateSmartCollectionDialog", openHandler),
);

// Platform-id → display-name lookup so the summary renders "SNES"
// instead of `#1`. Returns null when the store hasn't hydrated yet.
function platformLookup(id: number): string | null {
  return allPlatforms.value.find((p) => p.id === id)?.display_name ?? null;
}

const summary = computed(() =>
  summarizeSmartFilterCriteria(snapshot.value, t, platformLookup),
);

function close() {
  show.value = false;
}

async function submit() {
  if (submitting.value) return;
  if (!name.value.trim()) return;
  const trimmed = name.value.trim();
  if (collectionsStore.smartCollections.some((c) => c.name === trimmed)) {
    snackbar.error(
      t(
        "collection.name-exists",
        `A collection called "${trimmed}" already exists.`,
      ),
      { icon: "mdi-close-circle" },
    );
    return;
  }

  submitting.value = true;
  try {
    const data = await collectionApi.createSmartCollection({
      smartCollection: {
        name: name.value.trim(),
        description: description.value.trim() || undefined,
        filter_criteria: snapshot.value,
        is_public: isPublic.value,
      },
    });
    collectionsStore.addSmartCollection(data);
    snackbar.success(
      t("collection.smart-created", `Smart collection "${data.name}" created.`),
      { icon: "mdi-check-bold" },
    );
    show.value = false;
    router.push({
      name: ROUTES.SMART_COLLECTION,
      params: { collection: data.id },
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string; detail?: string } };
      message?: string;
    };
    snackbar.error(
      `${t("collection.smart-create-failed", "Failed to create smart collection")}: ${
        e?.response?.data?.msg ||
        e?.response?.data?.detail ||
        e?.message ||
        "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-playlist-plus"
    :width="mdAndUp ? 640 : '95vw'"
    @close="close"
  >
    <template #header>
      <span>{{
        t("collection.create-smart-collection", "Create smart collection")
      }}</span>
    </template>

    <template #content>
      <RForm v-model="formValid" class="r-v2-csc__form" @submit="submit">
        <div class="r-v2-csc__grid">
          <!-- Left column: editable fields -->
          <div class="r-v2-csc__fields">
            <RTextField
              v-model="name"
              :placeholder="t('collection.name', 'Name')"
              prefix-label="stacked"
              :rules="nameRules"
              required
              autofocus
            >
              <template #prefix-label>
                {{ t("collection.name", "Name") }}
              </template>
            </RTextField>

            <RTextField
              v-model="description"
              :placeholder="t('collection.description', 'Description')"
              prefix-label="stacked"
              multiline
              :rows="3"
              hide-details
            >
              <template #prefix-label>
                {{ t("collection.description", "Description") }}
              </template>
            </RTextField>

            <RSwitch
              v-model="isPublic"
              :label="
                isPublic
                  ? t('collection.public', 'Public')
                  : t('collection.private', 'Private')
              "
            />
          </div>

          <!-- Right column: criteria preview -->
          <aside class="r-v2-csc__preview">
            <header class="r-v2-csc__preview-head">
              <RIcon icon="mdi-filter-variant" size="14" />
              <span>{{
                t("collection.current-filters", "Current filters")
              }}</span>
            </header>
            <ul class="r-v2-csc__preview-list">
              <li
                v-for="row in summary"
                :key="row.key"
                class="r-v2-csc__preview-row"
              >
                <span class="r-v2-csc__preview-label">
                  <RIcon :icon="row.icon" size="14" />
                  <span>{{ row.label }}</span>
                  <RTag
                    v-if="row.logic"
                    tone="brand"
                    size="x-small"
                    class="r-v2-csc__preview-logic"
                  >
                    {{ row.logic }}
                  </RTag>
                </span>
                <div v-if="row.values?.length" class="r-v2-csc__preview-values">
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
          </aside>
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="submitting" @click="close">
        {{ t("common.cancel", "Cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-playlist-plus"
        :disabled="!name.trim() || submitting"
        :loading="submitting"
        @click="submit"
      >
        {{ t("common.create", "Create") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-csc__form {
  display: block;
}

.r-v2-csc__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}
@media (min-width: 640px) {
  .r-v2-csc__grid {
    grid-template-columns: 1.1fr 1fr;
    align-items: stretch;
  }
}

.r-v2-csc__fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.r-v2-csc__preview {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  min-height: 200px;
}

.r-v2-csc__preview-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.r-v2-csc__preview-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-csc__preview-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-csc__preview-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-csc__preview-logic {
  margin-left: 4px;
  text-transform: uppercase;
}

.r-v2-csc__preview-values {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 20px;
}
</style>
