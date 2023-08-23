<script setup>
import { ref, inject, onBeforeUnmount } from "vue";
import { useDisplay } from "vuetify";
import { updateRomApi, searchRomIGDBApi } from "@/services/api";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref();
const renameAsIGDB = ref(false);
const searching = ref(false);
const searchTerm = ref("");
const searchBy = ref("Name");
const matchedRoms = ref([]);
const selectedScrapSource = ref(0);

const emitter = inject("emitter");
emitter.on("showSearchRomDialog", (romToSearch) => {
  rom.value = romToSearch;
  searchTerm.value = romToSearch.file_name_no_tags;
  show.value = true;
  searchRomIGDB();
});

async function searchRomIGDB() {
  if (!searching.value) {
    searching.value = true;
    await searchRomIGDBApi(searchTerm.value, searchBy.value, rom.value)
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

async function updateRom(updatedData = { ...rom.value }) {
  show.value = false;
  emitter.emit("showLoadingDialog", { loading: true, scrim: true });

  await updateRomApi(rom.value, updatedData, renameAsIGDB.value)
    .then((response) => {
      emitter.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      emitter.emit("refreshView");
    })
    .catch((error) => {
      emitter.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

onBeforeUnmount(() => {
  emitter.off("showSearchRomDialog");
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="false"
    @click:outside="show = false"
    @keydown.esc="show = false"
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

          <v-col cols="8" xs="8" sm="9" md="9" lg="10">
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

          <v-col cols="2" xs="2" sm="2" md="2" lg="1">
            <v-btn
              @click="show = false"
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
              @keyup.enter="searchRomIGDB()"
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
              @click="searchRomIGDB()"
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
            v-for="rom in matchedRoms"
            :key="rom.file_name"
          >
            <v-hover v-slot="{ isHovering, props }">
              <v-card
                @click="updateRom((updatedData = rom))"
                v-bind="props"
                :class="{ 'on-hover': isHovering }"
                :elevation="isHovering ? 20 : 3"
              >
                <v-tooltip activator="parent" location="top" class="tooltip">{{
                  rom.r_name
                }}</v-tooltip>
                <v-img v-bind="props" :src="rom.url_cover" cover />
                <v-card-text>
                  <v-row class="pa-1">
                    <span class="d-inline-block text-truncate">{{
                      rom.r_name
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
  width: 900px;
  height: 640px;
}

.search-content-tablet {
  width: 570px;
  height: 640px;
}

.search-content-mobile {
  width: 85vw;
  height: 640px;
}
</style>
