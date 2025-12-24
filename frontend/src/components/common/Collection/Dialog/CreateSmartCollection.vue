<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { ref, computed } from "vue";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { getStatusKeyForText } from "@/utils";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const collectionsStore = storeCollections();
const { mdAndUp } = useDisplay();
const router = useRouter();
const show = ref(false);
const name = ref("");
const description = ref("");
const isPublic = ref(false);

const {
  searchTerm,
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterRA,
  filterMissing,
  filterVerified,
  selectedGenres,
  selectedFranchises,
  selectedCollections,
  selectedCompanies,
  selectedAgeRatings,
  selectedStatuses,
  selectedPlatforms,
  selectedRegions,
  selectedLanguages,
  genresLogic,
  franchisesLogic,
  collectionsLogic,
  companiesLogic,
  ageRatingsLogic,
  regionsLogic,
  languagesLogic,
} = storeToRefs(galleryFilterStore);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateSmartCollectionDialog", () => {
  if (!hasFilters.value) {
    emitter?.emit("snackbarShow", {
      msg: "Please apply some filters before creating a smart collection",
      icon: "mdi-information",
      color: "warning",
    });
    return;
  }
  show.value = true;
});

const hasFilters = computed(() => galleryFilterStore.isFiltered);

const filterSummary = computed(() => {
  const filters = [];

  if (searchTerm.value) filters.push(`Search: "${searchTerm.value}"`);
  if (selectedPlatforms.value && selectedPlatforms.value.length > 0)
    filters.push(
      `Platforms: ${selectedPlatforms.value.map((p) => p.name).join(", ")}`,
    );
  if (filterMatched.value) filters.push("Matched only");
  if (filterFavorites.value) filters.push("Favorites");
  if (filterDuplicates.value) filters.push("Duplicates");
  if (filterPlayables.value) filters.push("Playable");
  if (filterRA.value) filters.push("Has RetroAchievements");
  if (filterMissing.value) filters.push("Missing from filesystem");
  if (filterVerified.value) filters.push("Verified");
  if (selectedGenres.value && selectedGenres.value.length > 0)
    filters.push(`Genres: ${selectedGenres.value.join(", ")}`);
  if (selectedFranchises.value && selectedFranchises.value.length > 0)
    filters.push(`Franchises: ${selectedFranchises.value.join(", ")}`);
  if (selectedCollections.value && selectedCollections.value.length > 0)
    filters.push(`Collections: ${selectedCollections.value.join(", ")}`);
  if (selectedCompanies.value && selectedCompanies.value.length > 0)
    filters.push(`Companies: ${selectedCompanies.value.join(", ")}`);
  if (selectedAgeRatings.value && selectedAgeRatings.value.length > 0)
    filters.push(`Age Ratings: ${selectedAgeRatings.value.join(", ")}`);
  if (selectedStatuses.value && selectedStatuses.value.length > 0)
    filters.push(`Statuses: ${selectedStatuses.value.join(", ")}`);
  if (selectedRegions.value && selectedRegions.value.length > 0)
    filters.push(`Regions: ${selectedRegions.value.join(", ")}`);
  if (selectedLanguages.value && selectedLanguages.value.length > 0)
    filters.push(`Languages: ${selectedLanguages.value.join(", ")}`);

  return filters || ["No filters applied"];
});

function toggleCollectionVisibility() {
  isPublic.value = !isPublic.value;
}

function closeDialog() {
  show.value = false;
  name.value = "";
  description.value = "";
  isPublic.value = false;
}

async function createSmartCollection() {
  if (!name.value.trim()) {
    emitter?.emit("snackbarShow", {
      msg: "Please enter a name for the smart collection",
      icon: "mdi-alert",
      color: "error",
    });
    return;
  }

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  try {
    const filterCriteria: Record<
      string,
      number | boolean | string | string[] | number[] | (string | null)[] | null
    > = {};

    if (searchTerm.value) filterCriteria.search_term = searchTerm.value;
    if (selectedPlatforms.value && selectedPlatforms.value.length > 0)
      filterCriteria.platform_ids = selectedPlatforms.value.map((p) => p.id);
    if (filterMatched.value) filterCriteria.matched = true;
    if (filterFavorites.value) filterCriteria.favorite = true;
    if (filterDuplicates.value) filterCriteria.duplicate = true;
    if (filterPlayables.value) filterCriteria.playable = true;
    if (filterRA.value) filterCriteria.has_ra = true;
    if (filterMissing.value) filterCriteria.missing = true;
    if (filterVerified.value) filterCriteria.verified = true;
    if (selectedGenres.value && selectedGenres.value.length > 0) {
      filterCriteria.genres = selectedGenres.value;
      if (selectedGenres.value.length > 1)
        filterCriteria.genres_logic = genresLogic.value;
    }
    if (selectedFranchises.value && selectedFranchises.value.length > 0) {
      filterCriteria.franchises = selectedFranchises.value;
      if (selectedFranchises.value.length > 1)
        filterCriteria.franchises_logic = franchisesLogic.value;
    }
    if (selectedCollections.value && selectedCollections.value.length > 0) {
      filterCriteria.collections = selectedCollections.value;
      if (selectedCollections.value.length > 1)
        filterCriteria.collections_logic = collectionsLogic.value;
    }
    if (selectedCompanies.value && selectedCompanies.value.length > 0) {
      filterCriteria.companies = selectedCompanies.value;
      if (selectedCompanies.value.length > 1)
        filterCriteria.companies_logic = companiesLogic.value;
    }
    if (selectedAgeRatings.value && selectedAgeRatings.value.length > 0) {
      filterCriteria.age_ratings = selectedAgeRatings.value;
      if (selectedAgeRatings.value.length > 1)
        filterCriteria.age_ratings_logic = ageRatingsLogic.value;
    }
    if (selectedStatuses.value && selectedStatuses.value.length > 0) {
      const statusKeys = selectedStatuses.value
        .filter((s): s is string => s !== null)
        .map((s) => getStatusKeyForText(s))
        .filter((key) => key !== null);
      if (statusKeys.length > 0) {
        filterCriteria.selected_status = statusKeys;
      }
    }
    if (selectedRegions.value && selectedRegions.value.length > 0) {
      filterCriteria.regions = selectedRegions.value;
      if (selectedRegions.value.length > 1)
        filterCriteria.regions_logic = regionsLogic.value;
    }
    if (selectedLanguages.value && selectedLanguages.value.length > 0) {
      filterCriteria.languages = selectedLanguages.value;
      if (selectedLanguages.value.length > 1)
        filterCriteria.languages_logic = languagesLogic.value;
    }

    const { data } = await collectionApi.createSmartCollection({
      smartCollection: {
        name: name.value.trim(),
        description: description.value.trim() || undefined,
        filter_criteria: filterCriteria,
        is_public: isPublic.value,
      },
    });

    emitter?.emit("snackbarShow", {
      msg: `Smart collection "${name.value}" created successfully!`,
      icon: "mdi-check-circle",
      color: "green",
    });
    collectionsStore.addSmartCollection(data);
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    router.push({
      name: ROUTES.SMART_COLLECTION,
      params: { collection: data.id },
    });
    closeDialog();
  } catch (error) {
    console.error("Failed to create smart collection:", error);
    emitter?.emit("snackbarShow", {
      msg: "Failed to create smart collection",
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-playlist-plus"
    :width="mdAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-card-title>{{ t("collection.create-smart-collection") }}</v-card-title>
    </template>
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" lg="7" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="name"
                :label="t('collection.name')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="createSmartCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-textarea
                v-model="description"
                class="mt-1"
                :label="t('collection.description')"
                variant="outlined"
                rows="3"
                hide-details
                @keyup.enter="createSmartCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-btn
                :color="isPublic ? 'romm-green' : 'accent'"
                variant="outlined"
                @click="toggleCollectionVisibility"
              >
                <v-icon class="mr-2">
                  {{ isPublic ? "mdi-lock-open-variant" : "mdi-lock" }}
                </v-icon>
                {{
                  isPublic ? t("collection.public") : t("collection.private")
                }}
              </v-btn>
            </v-col>
          </v-row>
        </v-col>
        <v-col>
          <v-row class="pa-2 justify-center" no-gutters>
            <v-col class="filters-preview">
              <v-card variant="outlined" class="h-100">
                <v-card-title class="text-subtitle-1">
                  <v-icon class="mr-2"> mdi-filter </v-icon>
                  {{ t("collection.current-filters") }}
                </v-card-title>
                <v-card-text>
                  <ul class="mt-2 ml-4">
                    <li v-for="filter in filterSummary" :key="filter">
                      {{ filter }}
                    </li>
                  </ul>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #footer>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="!name.trim()"
            :variant="!name.trim() ? 'plain' : 'flat'"
            @click="createSmartCollection"
          >
            {{ t("common.create") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
<style scoped>
.filters-preview {
  min-width: 240px;
  min-height: 330px;
  max-width: 240px;
  max-height: 330px;
}
</style>
