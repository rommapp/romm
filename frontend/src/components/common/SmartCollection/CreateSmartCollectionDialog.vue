<script setup lang="ts">
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import { inject } from "vue";

// Props
const { t } = useI18n();
const collectionsStore = storeCollections();
const galleryFilterStore = storeGalleryFilter();
const emitter = inject<Emitter<Events>>("emitter");

// State
const show = ref(false);
const loading = ref(false);
const name = ref("");
const description = ref("");
const isPublic = ref(false);

// Get current filter state
const {
  searchTerm,
  filterUnmatched,
  filterMatched,
  filterFavourites,
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

// Computed
const hasFilters = computed(() => galleryFilterStore.isFiltered);

const filterSummary = computed(() => {
  const filters = [];

  if (searchTerm.value) filters.push(`Search: "${searchTerm.value}"`);
  if (selectedPlatform.value)
    filters.push(`Platform: ${selectedPlatform.value.name}`);
  if (filterMatched.value) filters.push("Matched only");
  if (filterUnmatched.value) filters.push("Unmatched only");
  if (filterFavourites.value) filters.push("Favourites");
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

  return filters.length > 0 ? filters.join("; ") : "No filters applied";
});

// Methods
function openDialog() {
  if (!hasFilters.value) {
    emitter?.emit("snackbarShow", {
      msg: "Please apply some filters before creating a smart collection",
      icon: "mdi-information",
      color: "warning",
    });
    return;
  }

  show.value = true;
  name.value = "";
  description.value = "";
  isPublic.value = false;
}

function closeDialog() {
  show.value = false;
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

  loading.value = true;

  try {
    // Build filter criteria object from current state
    const filterCriteria: Record<string, any> = {};

    if (searchTerm.value) filterCriteria.search_term = searchTerm.value;
    if (selectedPlatform.value)
      filterCriteria.platform_id = selectedPlatform.value.id;
    if (filterMatched.value) filterCriteria.matched = true;
    if (filterUnmatched.value) filterCriteria.matched = false;
    if (filterFavourites.value) filterCriteria.favourite = true;
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
      filterCriteria.selected_status = selectedStatus.value;
    if (selectedRegion.value)
      filterCriteria.selected_region = selectedRegion.value;
    if (selectedLanguage.value)
      filterCriteria.selected_language = selectedLanguage.value;

    await collectionsStore.createSmartCollection({
      name: name.value.trim(),
      description: description.value.trim() || undefined,
      filter_criteria: filterCriteria,
      is_public: isPublic.value,
    });

    emitter?.emit("snackbarShow", {
      msg: `Smart collection "${name.value}" created successfully!`,
      icon: "mdi-check-circle",
      color: "green",
    });

    closeDialog();
  } catch (error: any) {
    console.error("Failed to create smart collection:", error);
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || "Failed to create smart collection",
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    loading.value = false;
  }
}

// Expose methods for parent components
defineExpose({
  openDialog,
});
</script>

<template>
  <v-dialog v-model="show" max-width="600px" persistent>
    <v-card>
      <v-card-title class="text-h5">
        <v-icon class="mr-2">mdi-playlist-plus</v-icon>
        Create Smart Collection
      </v-card-title>

      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="name"
                label="Collection Name"
                required
                :disabled="loading"
                prepend-icon="mdi-tag"
              />
            </v-col>

            <v-col cols="12">
              <v-textarea
                v-model="description"
                label="Description (optional)"
                rows="3"
                :disabled="loading"
                prepend-icon="mdi-text"
              />
            </v-col>

            <v-col cols="12">
              <v-switch
                v-model="isPublic"
                label="Make this collection public"
                :disabled="loading"
                color="primary"
              />
            </v-col>

            <v-col cols="12">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon class="mr-2">mdi-filter</v-icon>
                  Current Filters
                </v-card-title>
                <v-card-text>
                  <div class="text-body-2 text-medium-emphasis">
                    {{ filterSummary }}
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn text @click="closeDialog" :disabled="loading"> Cancel </v-btn>
        <v-btn
          color="primary"
          @click="createSmartCollection"
          :loading="loading"
          :disabled="!name.trim()"
        >
          Create Smart Collection
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
