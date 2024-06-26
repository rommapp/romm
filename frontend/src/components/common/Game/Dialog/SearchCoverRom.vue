<script setup lang="ts">
import type { SearchCoverSchema, SearchRomSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const { xs, lgAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const theme = useTheme();
const rom = ref<SimpleRom | null>(null);
const searching = ref(false);
const searchTerm = ref("");
const games = ref<SearchCoverSchema[]>();
const panels = ref([0]);
const panelIndex = ref(0);
const emitter = inject<Emitter<Events>>("emitter");
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

  console.log(url_cover);
  console.log(url_cover.replace("thumb", "grid"));

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
      emitter?.emit("refreshView", null);
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
    :empty-state-condition="games?.length == 0"
    empty-state-type="game"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="lgAndUp ? '90vh' : '775px'"
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="10" sm="11">
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
        <v-expansion-panel v-for="game in games" :key="game.name">
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
                  >
                    <template #error>
                      <v-img
                        :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
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
