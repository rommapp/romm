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
  filterUnmatched,
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterRA,
  filterMissing,
  filterVerified,
  selectedGenre,
  selectedFranchise,
  selectedCollection,
  selectedCompany,
  selectedAgeRating,
  selectedStatus,
  selectedPlatform,
  selectedRegion,
  selectedLanguage,
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
  if (selectedPlatform.value)
    filters.push(`Platform: ${selectedPlatform.value.name}`);
  if (filterMatched.value) filters.push("Matched only");
  if (filterUnmatched.value) filters.push("Unmatched only");
  if (filterFavorites.value) filters.push("Favorites");
  if (filterDuplicates.value) filters.push("Duplicates");
  if (filterPlayables.value) filters.push("Playable");
  if (filterRA.value) filters.push("Has RetroAchievements");
  if (filterMissing.value) filters.push("Missing from filesystem");
  if (filterVerified.value) filters.push("Verified");
  if (selectedGenre.value) filters.push(`Genre: ${selectedGenre.value}`);
  if (selectedFranchise.value)
    filters.push(`Franchise: ${selectedFranchise.value}`);
  if (selectedCollection.value)
    filters.push(`Collection: ${selectedCollection.value}`);
  if (selectedCompany.value) filters.push(`Company: ${selectedCompany.value}`);
  if (selectedAgeRating.value)
    filters.push(`Age Rating: ${selectedAgeRating.value}`);
  if (selectedStatus.value) filters.push(`Status: ${selectedStatus.value}`);
  if (selectedRegion.value) filters.push(`Region: ${selectedRegion.value}`);
  if (selectedLanguage.value)
    filters.push(`Language: ${selectedLanguage.value}`);

  return filters || ["No filters applied"];
});

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
    const filterCriteria: Record<string, number | boolean | string | null> = {};

    if (searchTerm.value) filterCriteria.search_term = searchTerm.value;
    if (selectedPlatform.value)
      filterCriteria.platform_id = selectedPlatform.value.id;
    if (filterMatched.value) filterCriteria.matched = true;
    if (filterUnmatched.value) filterCriteria.matched = false;
    if (filterFavorites.value) filterCriteria.favorite = true;
    if (filterDuplicates.value) filterCriteria.duplicate = true;
    if (filterPlayables.value) filterCriteria.playable = true;
    if (filterRA.value) filterCriteria.has_ra = true;
    if (filterMissing.value) filterCriteria.missing = true;
    if (filterVerified.value) filterCriteria.verified = true;
    if (selectedGenre.value)
      filterCriteria.selected_genre = selectedGenre.value;
    if (selectedFranchise.value)
      filterCriteria.selected_franchise = selectedFranchise.value;
    if (selectedCollection.value)
      filterCriteria.selected_collection = selectedCollection.value;
    if (selectedCompany.value)
      filterCriteria.selected_company = selectedCompany.value;
    if (selectedAgeRating.value)
      filterCriteria.selected_age_rating = selectedAgeRating.value;
    if (selectedStatus.value)
      filterCriteria.selected_status = getStatusKeyForText(
        selectedStatus.value,
      );
    if (selectedRegion.value)
      filterCriteria.selected_region = selectedRegion.value;
    if (selectedLanguage.value)
      filterCriteria.selected_language = selectedLanguage.value;

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
              <v-switch
                v-model="isPublic"
                :label="t('collection.public-desc')"
                color="primary"
                hide-details
              />
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
    <template #append>
      <v-divider />
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
