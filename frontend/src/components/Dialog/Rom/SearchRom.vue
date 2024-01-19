<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay } from "vuetify";

import type { IGDBRomType } from "@/__generated__";
import apiRom from "@/services/apiRom";
import storeRoms, { type Rom } from "@/stores/roms";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<Rom | null>(null);
const romsStore = storeRoms();
const renameAsIGDB = ref(false);
const searching = ref(false);
const searchTerm = ref("");
const searchBy = ref("Name");
const matchedRoms = ref<IGDBRomType[]>([]);
const selectedScrapSource = ref(0);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchRomDialog", (romToSearch) => {
  rom.value = romToSearch;
  searchTerm.value = romToSearch.file_name_no_tags;
  show.value = true;
  searchRom();
});

// Functions
async function searchRom() {
  if (!rom.value) return;

  if (!searching.value) {
    searching.value = true;
    await apiRom
      .searchRom({
        romId: rom.value.id,
        source: "igdb",
        searchTerm: searchTerm.value,
        searchBy: searchBy.value,
      })
      .then((response) => {
        matchedRoms.value = response.data.roms;
      })
      .catch((error) => {
        console.log(error);
      })
      .finally(() => {
        searching.value = false;
      });
  }
}

async function updateRom(matchedRom: IGDBRomType) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  rom.value.igdb_id = matchedRom.igdb_id;
  rom.value.name = matchedRom.name;
  rom.value.slug = matchedRom.slug;
  rom.value.summary = matchedRom.summary;
  rom.value.url_cover = matchedRom.url_cover;
  rom.value.url_screenshots = matchedRom.url_screenshots;

  await apiRom
    .updateRom({ rom: rom.value, renameAsIGDB: renameAsIGDB.value })
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

function closeDialog() {
  show.value = false;
}

onBeforeUnmount(() => {
  emitter?.off("showSearchRomDialog");
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card
      :class="{
        'search-content': lgAndUp,
        'search-content-tablet': mdAndDown,
        'search-content-mobile': xs,
      }"
      rounded="0"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="2" xs="2" sm="1" md="1" lg="1">
            <v-icon icon="mdi-search-web" class="ml-5" />
          </v-col>

          <v-col cols="8" xs="8" sm="9" md="10" lg="10">
            <v-item-group mandatory v-model="selectedScrapSource">
              <v-item v-slot="{ isSelected, toggle }">
                <v-chip
                  class="mx-1"
                  :color="isSelected ? 'romm-accent-1' : 'romm-gray'"
                  variant="outlined"
                  label
                  @click="toggle"
                  >IGDB</v-chip
                >
              </v-item>
              <!-- TODO: Ready item group to scrape from different sources -->
              <!-- <v-item v-slot="{ isSelected, toggle }" disabled>
                <v-chip class="mx-1" :color="isSelected ? 'romm-accent-1' : 'romm-gray'" variant="outlined" label @click="toggle"
                  >ScreenScraper</v-chip
                >
              </v-item>
              <v-item v-slot="{ isSelected, toggle }" disabled>
                <v-chip class="mx-1" :color="isSelected ? 'romm-accent-1' : 'romm-gray'" variant="outlined" label @click="toggle"
                  >MobyGames</v-chip
                >
              </v-item>
              <v-item v-slot="{ isSelected, toggle }" disabled>
                <v-chip class="mx-1" :color="isSelected ? 'romm-accent-1' : 'romm-gray'" variant="outlined" label @click="toggle"
                  >RAWG</v-chip
                >
              </v-item> -->
            </v-item-group>
          </v-col>

          <v-col cols="2" xs="2" sm="2" md="1" lg="1">
            <v-btn
              @click="closeDialog"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-toolbar density="compact" class="bg-primary">
        <v-row class="align-center" no-gutters>
          <v-col cols="7" xs="7" sm="8" md="8" lg="9">
            <v-text-field
              autofocus
              @keyup.enter="searchRom()"
              @click:clear="searchTerm = ''"
              class="bg-terciary"
              v-model="searchTerm"
              label="search"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="3" xs="3" sm="2" md="2" lg="2">
            <v-select
              label="by"
              class="bg-terciary"
              :items="['ID', 'Name']"
              v-model="searchBy"
              hide-details
            />
          </v-col>
          <v-col cols="2" xs="2" sm="2" md="2" lg="1">
            <v-btn
              type="submit"
              @click="searchRom()"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-search-web"
              block
              :disabled="searching"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text class="pa-1 scroll">
        <v-row
          class="justify-center loader-searching"
          v-show="searching"
          no-gutters
        >
          <v-progress-circular
            :width="2"
            :size="40"
            color="romm-accent-1"
            indeterminate
          />
        </v-row>
        <v-row
          class="justify-center no-results-searching"
          v-show="!searching && matchedRoms.length == 0"
          no-gutters
        >
          <span>No results found</span>
        </v-row>
        <v-row no-gutters>
          <v-col
            class="pa-1"
            cols="4"
            xs="4"
            sm="3"
            md="3"
            lg="2"
            v-show="!searching"
            v-for="matchedRom in matchedRoms"
          >
            <v-hover v-slot="{ isHovering, props }">
              <v-card
                @click="updateRom(matchedRom)"
                v-bind="props"
                class="matched-rom"
                :class="{ 'on-hover': isHovering }"
                :elevation="isHovering ? 20 : 3"
              >
                <v-tooltip activator="parent" location="top" class="tooltip">{{
                  matchedRom.name
                }}</v-tooltip>
                <v-img
                  v-bind="props"
                  :src="matchedRom.url_cover"
                  :aspect-ratio="3 / 4"
                />
                <v-card-text>
                  <v-row class="pa-1">
                    <span class="d-inline-block text-truncate">{{
                      matchedRom.name
                    }}</span>
                  </v-row>
                </v-card-text>
              </v-card>
            </v-hover>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-toolbar class="bg-terciary" density="compact">
        <v-checkbox
          v-model="renameAsIGDB"
          label="Rename rom"
          class="ml-3"
          hide-details
        />
      </v-toolbar>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
.scroll {
  overflow-y: scroll;
}
.loader-searching,
.no-results-searching {
  margin-top: 200px;
}

.search-content {
  width: 60vw;
  height: 80vh;
}

.search-content-tablet {
  width: 75vw;
  height: 640px;
}

.search-content-mobile {
  width: 85vw;
  height: 640px;
}
.matched-rom {
  transition-property: all;
  transition-duration: 0.1s;
}
.matched-rom.on-hover {
  z-index: 1 !important;
  opacity: 1;
  transform: scale(1.05);
}
</style>
