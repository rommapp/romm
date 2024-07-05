<script setup lang="ts">
import type { SearchCoverSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import sgdbApi from "@/services/api/sgdb";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { lgAndUp } = useDisplay();
const show = ref(false);
const searching = ref(false);
const searchTerm = ref("");
const coverType = ref("all");
const covers = ref<SearchCoverSchema[]>([]);
const filteredCovers = ref<SearchCoverSchema[]>();
const panels = ref([0]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchCoverDialog", (term) => {
  searchTerm.value = term;
  show.value = true;
  if (searchTerm.value) searchCovers();
});

// Functions
async function searchCovers() {
  covers.value = [];

  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();

  if (!searching.value) {
    searching.value = true;
    await sgdbApi
      .searchCover({
        searchTerm: searchTerm.value,
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
                      (resource) => resource.type === coverType.value
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
                  (resource) => resource.type === coverType.value
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
  searchTerm.value = "";
}

onBeforeUnmount(() => {
  emitter?.off("showSearchCoverDialog");
});
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-image-search-outline"
    :loading-condition="searching"
    :empty-state-condition="filteredCovers?.length == 0"
    empty-state-type="game"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="lgAndUp ? '90vh' : '775px'"
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="8" sm="9">
          <v-text-field
            id="search-text-field"
            @keyup.enter="searchCovers()"
            @click:clear="searchTerm = ''"
            class="bg-terciary"
            v-model="searchTerm"
            :disabled="searching"
            label="Search"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="2" sm="2">
          <v-select
            :disabled="searching"
            v-model="coverType"
            hide-details
            label="Type"
            @update:model-value="filterCovers"
            :items="['all', 'static', 'animated']"
          />
        </v-col>
        <v-col>
          <v-btn
            type="submit"
            @click="searchCovers()"
            class="bg-terciary"
            rounded="0"
            variant="text"
            icon="mdi-search-web"
            block
            :disabled="searching"
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-expansion-panels
        :model-value="panels"
        multiple
        flat
        rounded="0"
        variant="accordion"
      >
        <v-expansion-panel v-for="game in filteredCovers" :key="game.name">
          <v-expansion-panel-title class="bg-terciary">
            <v-row no-gutters class="justify-center">
              <v-list-item class="pa-0">{{ game.name }}</v-list-item>
            </v-row>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="pa-0">
            <v-row no-gutters>
              <v-col
                class="pa-1"
                cols="4"
                sm="3"
                md="2"
                v-for="resource in game.resources"
              >
                <v-hover v-slot="{ isHovering, props: hoverProps }">
                  <v-img
                    v-bind="hoverProps"
                    :class="{ 'on-hover': isHovering }"
                    class="transform-scale pointer"
                    @click="selectCover(resource.url)"
                    :aspect-ratio="2 / 3"
                    :src="resource.thumb"
                    cover
                  >
                    <template #error>
                      <v-img
                        :src="resource.url"
                        cover
                        :aspect-ratio="2 / 3"
                      ></v-img>
                    </template>
                    <template #placeholder>
                      <div
                        class="d-flex align-center justify-center fill-height"
                      >
                        <v-progress-circular
                          :width="2"
                          :size="40"
                          color="romm-accent-1"
                          indeterminate
                        />
                      </div>
                    </template>
                  </v-img>
                </v-hover>
              </v-col>
            </v-row>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>
  </r-dialog>
</template>
