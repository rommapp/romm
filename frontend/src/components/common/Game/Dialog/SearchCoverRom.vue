<script setup lang="ts">
import type { SearchCoverSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { lgAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const rom = ref<SimpleRom | null>(null);
const searching = ref(false);
const searchTerm = ref("");
const games = ref<SearchCoverSchema[]>();
const filteredGames = ref<SearchCoverSchema[]>();
const panels = ref([0]);
const emitter = inject<Emitter<Events>>("emitter");
const type = ref("all");
emitter?.on("showSearchCoverDialog", (romToSearch) => {
  rom.value = romToSearch;
  searchTerm.value = romToSearch.name || romToSearch.file_name_no_tags || "";
  show.value = true;
  searchCovers();
});

// Functions
async function searchCovers() {
  games.value = undefined;

  if (!rom.value) return;

  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();

  if (!searching.value) {
    searching.value = true;
    await romApi
      .searchCover({
        searchTerm: searchTerm.value,
      })
      .then((response) => {
        games.value = response.data;
        filteredGames.value = games.value
          .map((game) => {
            return {
              ...game,
              resources:
                type.value === "all"
                  ? game.resources
                  : game.resources.filter(
                      (resource) => resource.type === type.value
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

async function updateCover(url_cover: string) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  rom.value.url_cover = url_cover.replace("thumb", "grid");

  await romApi
    .updateRom({ rom: rom.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Rom updated successfully!",
        icon: "mdi-check-bold",
        color: "green",
      });
      romsStore.update(data);
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

function filterCovers() {
  if (games.value) {
    filteredGames.value = games.value
      .map((game) => {
        return {
          ...game,
          resources:
            type.value === "all"
              ? game.resources
              : game.resources.filter(
                  (resource) => resource.type === type.value
                ),
        };
      })
      .filter((item) => item.resources.length > 0);
  }
}

function closeDialog() {
  show.value = false;
  games.value = undefined;
}

onBeforeUnmount(() => {
  emitter?.off("showSearchCoverDialog");
});
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-image-outline"
    :loading-condition="searching"
    :empty-state-condition="filteredGames?.length == 0"
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
            label="Search"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="2" sm="2">
          <v-select
            :disabled="searching"
            v-model="type"
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
        <v-expansion-panel v-for="game in filteredGames" :key="game.name">
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
                    @click="updateCover(resource.url)"
                    :aspect-ratio="2 / 3"
                    :src="resource.thumb"
                    cover
                  >
                    <template #error>
                      <v-img :src="resource.url" cover :aspect-ratio="2 / 3"></v-img>
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
