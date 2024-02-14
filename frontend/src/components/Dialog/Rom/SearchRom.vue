<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeRoms, { type Rom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<Rom | null>(null);
const romsStore = storeRoms();
const renameAsIGDB = ref(false);
const searching = ref(false);
const searchTerm = ref("");
const searchBy = ref("Name");
const searchExtended = ref(false);
const matchedRoms = ref<SearchRomSchema[]>([]);
const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSearchRomDialog", (romToSearch) => {
  rom.value = romToSearch;
  searchTerm.value = romToSearch.file_name_no_tags;
  show.value = true;
  searchRom();
});

// Functions
function toggleExtended() {
  searchExtended.value = !searchExtended.value;
}

async function searchRom() {
  if (!rom.value) return;

  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();

  if (!searching.value) {
    searching.value = true;
    await romApi
      .searchRom({
        romId: rom.value.id,
        searchTerm: searchTerm.value,
        searchBy: searchBy.value,
        searchExtended: searchExtended.value,
      })
      .then((response) => {
        matchedRoms.value = response.data;
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

async function updateRom(matchedRom: SearchRomSchema) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  Object.assign(rom.value, matchedRom);

  await romApi
    .updateRom({ rom: rom.value, renameAsIGDB: renameAsIGDB.value })
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
  searchBy.value = "Name";
  searchExtended.value = false;
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
          <v-col cols="5" xs="5" sm="5" md="6" lg="8">
            <v-text-field
              id="search-text-field"
              @keyup.enter="searchRom()"
              @click:clear="searchTerm = ''"
              class="bg-terciary"
              v-model="searchTerm"
              label="search"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="3" xs="3" sm="3" md="2" lg="2">
            <v-select
              label="by"
              class="bg-terciary"
              :items="['ID', 'Name']"
              v-model="searchBy"
              hide-details
            />
          </v-col>

          <v-col cols="2" xs="2" sm="2" md="2" lg="1">
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Extended search to match by alternative names. This will take longer."
              open-delay="500"
              ><template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  @click="toggleExtended"
                  class="bg-terciary"
                  :color="searchExtended ? 'romm-accent-1' : ''"
                  rounded="0"
                  variant="tonal"
                  icon="mdi-layers-search-outline"
                  block /></template></v-tooltip
          ></v-col>
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
          class="justify-center align-center loader-searching fill-height"
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
          class="justify-center align-center loader-searching fill-height"
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
                <v-hover v-slot="{ isHovering, props }" open-delay="800">
                  <v-img
                    v-bind="props"
                    :src="
                      !matchedRom.url_cover
                        ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                        : matchedRom.url_cover
                    "
                    :lazy-src="
                      !matchedRom.url_cover
                        ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
                        : matchedRom.url_cover
                    "
                    :aspect-ratio="3 / 4"
                  >
                    <template v-slot:placeholder>
                      <div
                        class="d-flex align-center justify-center fill-height"
                      >
                        <v-progress-circular
                          color="romm-accent-1"
                          :width="2"
                          indeterminate
                        />
                      </div>
                    </template>
                    <v-row no-gutters class="text-white px-1">
                      <v-chip class="translucent mr-1 mt-1" label v-if="matchedRom.igdb_id">
                        <span> IGDB </span>
                      </v-chip>
                      <v-chip class="translucent mr-1 mt-1" label v-if="matchedRom.moby_id">
                        <span> Moby </span>
                      </v-chip>
                    </v-row>
                  </v-img></v-hover
                >
                <v-card-text>
                  <v-row class="pa-1 align-center">
                    <v-col class="pa-0 ml-1 text-truncate">
                      <span>{{ matchedRom.name }}</span>
                    </v-col>
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
.scroll {
  overflow-y: scroll;
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
  transform: scale(1.05);
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
}
</style>
