<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useDisplay } from "vuetify";
import type { SearchCoverSchema } from "@/__generated__";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import RDialog from "@/components/common/RDialog.vue";
import sgdbApi from "@/services/api/sgdb";
import storeGalleryView from "@/stores/galleryView";
import type { Events } from "@/types/emitter";

const { lgAndUp } = useDisplay();
const galleryViewStore = storeGalleryView();
const show = ref(false);
const searching = ref(false);
const searchText = ref("");
const coverType = ref("all");
const platformIdRef = ref<number | undefined>(undefined);
const covers = ref<SearchCoverSchema[]>([]);
const filteredCovers = ref<SearchCoverSchema[]>();
const panels = ref([0]);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchCoverDialog", handleShowSearchCoverDialog);

const computedAspectRatio = computed(() => {
  return galleryViewStore.getAspectRatio({
    platformId: platformIdRef.value,
    boxartStyle: "cover_path",
  });
});

function handleShowSearchCoverDialog({
  term,
  platformId,
}: {
  term: string;
  platformId?: number;
}) {
  searchText.value = term;
  show.value = true;
  if (platformId) platformIdRef.value = platformId;
  if (searchText.value) searchCovers();
}

async function searchCovers() {
  covers.value = [];

  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();

  if (!searching.value) {
    searching.value = true;
    await sgdbApi
      .searchCover({
        searchTerm: searchText.value,
      })
      .then((response) => {
        covers.value = response.data;
        filteredCovers.value = covers.value
          .map((game) => {
            return {
              ...game,
              resources:
                coverType.value === "all"
                  ? game.resources
                  : game.resources.filter(
                      (resource) => resource.type === coverType.value,
                    ),
            };
          })
          .filter((item) => item.resources.length > 0);
      })
      .catch((error) => {
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
      })
      .finally(() => {
        searching.value = false;
      });
  }
}

async function selectCover(url_cover: string) {
  emitter?.emit("updateUrlCover", url_cover.replace("thumb", "grid"));
  closeDialog();
}

function filterCovers() {
  if (covers.value) {
    filteredCovers.value = covers.value
      .map((game) => {
        return {
          ...game,
          resources:
            coverType.value === "all"
              ? game.resources
              : game.resources.filter(
                  (resource) => resource.type === coverType.value,
                ),
        };
      })
      .filter((item) => item.resources.length > 0);
  }
}

function closeDialog() {
  show.value = false;
  covers.value = [];
  filteredCovers.value = [];
  searchText.value = "";
}

onBeforeUnmount(() => {
  emitter?.off("showSearchCoverDialog", handleShowSearchCoverDialog);
});
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-image-search-outline"
    :loading-condition="searching"
    :empty-state-condition="filteredCovers?.length == 0"
    empty-state-type="game"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    @close="closeDialog"
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="8" sm="9">
          <v-text-field
            id="search-text-field"
            v-model="searchText"
            class="bg-toplayer"
            :disabled="searching"
            label="Search"
            hide-details
            clearable
            @keyup.enter="searchCovers"
            @click:clear="searchText = ''"
          />
        </v-col>
        <v-col cols="2" sm="2">
          <v-select
            v-model="coverType"
            :disabled="searching"
            hide-details
            label="Type"
            :items="['all', 'static', 'animated']"
            @update:model-value="filterCovers"
          />
        </v-col>
        <v-col>
          <v-btn
            type="submit"
            class="bg-toplayer"
            variant="text"
            icon="mdi-search-web"
            block
            rounded="0"
            :disabled="searching"
            @click="searchCovers"
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-expansion-panels
        :model-value="panels"
        multiple
        flat
        variant="accordion"
      >
        <v-expansion-panel v-for="game in filteredCovers" :key="game.name">
          <v-expansion-panel-title class="bg-toplayer">
            <v-row no-gutters class="justify-center">
              <v-list-item class="pa-0">
                {{ game.name }}
              </v-list-item>
            </v-row>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="py-1">
            <v-row no-gutters>
              <v-col
                v-for="resource in game.resources"
                :key="resource.url"
                class="pa-1"
                cols="4"
                sm="3"
                md="2"
              >
                <v-img
                  class="transform-scale pointer"
                  :aspect-ratio="computedAspectRatio"
                  :src="resource.thumb"
                  cover
                  @click="selectCover(resource.url)"
                >
                  <template #error>
                    <v-img
                      :src="resource.url"
                      cover
                      :aspect-ratio="computedAspectRatio"
                    />
                  </template>
                  <template #placeholder>
                    <Skeleton type="image" />
                  </template>
                </v-img>
              </v-col>
            </v-row>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>
  </RDialog>
</template>
<style lang="css">
.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
