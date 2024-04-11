<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import SelectSourceDialog from "@/components/Dialog/Rom/MatchRom/SelectSource.vue";
import romApi from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
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
const filteredMatchedRoms = ref<SearchRomSchema[]>();
const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const isIGDBFiltered = ref(true);
const isMobyFiltered = ref(true);
emitter?.on("showMatchRomDialog", (romToSearch) => {
  rom.value = romToSearch;
  searchTerm.value = romToSearch.name || romToSearch.file_name_no_tags || "";
  show.value = true;
  searchRom();
});

// Functions
function toggleSourceFilter(source: string) {
  if (source == "igdb") {
    isIGDBFiltered.value = !isIGDBFiltered.value;
  } else if (source == "moby") {
    isMobyFiltered.value = !isMobyFiltered.value;
  }
  filteredMatchedRoms.value = matchedRoms.value.filter((rom) => {
    if (
      (rom.igdb_id && isIGDBFiltered.value) ||
      (rom.moby_id && isMobyFiltered.value)
    ) {
      return true;
    }
  });
}

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
        filteredMatchedRoms.value = matchedRoms.value.filter((rom) => {
          if (
            (rom.igdb_id && isIGDBFiltered.value) ||
            (rom.moby_id && isMobyFiltered.value)
          ) {
            return true;
          }
        });
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

async function selectMatched(matchedRom: SearchRomSchema) {
  if (!rom.value) return;

  if (matchedRom.igdb_id && matchedRom.moby_id) {
    emitter?.emit("showSelectSourceDialog", matchedRom);
  } else {
    if (matchedRom.igdb_id) {
      updateRom(
        Object.assign(matchedRom, { url_cover: matchedRom.igdb_url_cover })
      );
    } else if (matchedRom.moby_id) {
      updateRom(
        Object.assign(matchedRom, { url_cover: matchedRom.moby_url_cover })
      );
    }
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
  emitter?.off("showMatchRomDialog");
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
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-search-web" class="ml-5" />
            <span class="ml-4">Filter:</span>

            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Filter IGDB matches"
              open-delay="500"
              ><template v-slot:activator="{ props }">
                <v-avatar
                  v-if="heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED"
                  @click="toggleSourceFilter('igdb')"
                  v-bind="props"
                  class="ml-3 source-filter"
                  :class="{ filtered: isIGDBFiltered }"
                  size="30"
                  rounded="1"
                >
                  <v-img src="/assets/scrappers/igdb.png" />
                </v-avatar> </template
            ></v-tooltip>

            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Filter Mobygames matches"
              open-delay="500"
              ><template v-slot:activator="{ props }">
                <v-avatar
                  v-if="heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED"
                  @click="toggleSourceFilter('moby')"
                  v-bind="props"
                  class="ml-3 source-filter"
                  :class="{ filtered: isMobyFiltered }"
                  size="30"
                  rounded="1"
                >
                  <v-img src="/assets/scrappers/moby.png" />
                </v-avatar> </template
            ></v-tooltip>
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
              class="bg-terciary"
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
            v-for="matchedRom in filteredMatchedRoms"
          >
            <v-hover v-slot="{ isHovering, props }">
              <v-card
                @click="selectMatched(matchedRom)"
                v-bind="props"
                class="matched-rom"
                :class="{ 'on-hover': isHovering }"
                :elevation="isHovering ? 20 : 3"
              >
                <v-hover v-slot="{ isHovering, props }" open-delay="800">
                  <v-img
                    v-bind="props"
                    :src="
                      !matchedRom.igdb_url_cover && !matchedRom.moby_url_cover
                        ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                        : matchedRom.igdb_url_cover
                        ? matchedRom.igdb_url_cover
                        : matchedRom.moby_url_cover
                    "
                    :lazy-src="
                      !matchedRom.igdb_url_cover && !matchedRom.moby_url_cover
                        ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
                        : matchedRom.igdb_url_cover
                        ? matchedRom.igdb_url_cover
                        : matchedRom.moby_url_cover
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
                    <v-expand-transition>
                      <div
                        v-if="
                          isHovering ||
                          (!matchedRom.igdb_url_cover &&
                            !matchedRom.moby_url_cover)
                        "
                        class="translucent text-caption"
                      >
                        <v-list-item>{{ matchedRom.name }}</v-list-item>
                      </div>
                    </v-expand-transition>
                    <v-row no-gutters class="text-white pa-1">
                      <v-tooltip
                        location="top"
                        class="tooltip"
                        transition="fade-transition"
                        text="IGDB matched"
                        open-delay="500"
                        ><template v-slot:activator="{ props }">
                          <v-avatar
                            v-bind="props"
                            v-if="matchedRom.igdb_id"
                            size="30"
                            rounded="1"
                          >
                            <v-img
                              src="/assets/scrappers/igdb.png"
                            /> </v-avatar></template
                      ></v-tooltip>
                      <v-tooltip
                        location="top"
                        class="tooltip"
                        transition="fade-transition"
                        text="Mobygames matched"
                        open-delay="500"
                        ><template v-slot:activator="{ props }">
                          <v-avatar
                            v-bind="props"
                            v-if="matchedRom.moby_id"
                            class="ml-1"
                            size="30"
                            rounded="1"
                          >
                            <v-img
                              src="/assets/scrappers/moby.png"
                            /> </v-avatar></template
                      ></v-tooltip>
                    </v-row> </v-img
                ></v-hover>
                <v-card-text>
                  <v-row class="pa-1 align-center">
                    <v-col class="pa-0 ml-1 text-truncate">
                      <span :title="matchedRom.name">{{
                        matchedRom.name
                      }}</span>
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

  <select-source-dialog id="select-source-dialog" @update-rom="updateRom" />
</template>

<style scoped>
#select-source-dialog {
  z-index: 9999 !important;
}

.scroll {
  overflow-y: scroll;
}

.search-content {
  width: 65vw;
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
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
.source-filter {
  cursor: pointer;
  opacity: 0.4;
}
.source-filter.filtered {
  opacity: 1;
}
</style>
