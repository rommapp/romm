<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

type matchedSource = {
  url_cover: string | undefined;
  name: string;
};

// Props
const { xs, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const searching = ref(false);
const searchTerm = ref("");
const theme = useTheme();
const searchBy = ref("Name");
const matchedRoms = ref<SearchRomSchema[]>([]);
const filteredMatchedRoms = ref<SearchRomSchema[]>();
const emitter = inject<Emitter<Events>>("emitter");
const showSelectSource = ref(false);
const renameAsSource = ref(false);
const selectedRom = ref<SearchRomSchema>();
const sources = ref<matchedSource[]>([]);
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
  if (source == "igdb" && heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED) {
    isIGDBFiltered.value = !isIGDBFiltered.value;
  } else if (
    source == "moby" &&
    heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED
  ) {
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

async function searchRom() {
  showSelectSource.value = false;
  sources.value = [];
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

function showSources(matchedRom: SearchRomSchema) {
  if (!rom.value) return;

  var cardContent = document.getElementById("r-dialog-content");
  if (cardContent) {
    cardContent.scrollTop = 0;
  }
  showSelectSource.value = true;
  selectedRom.value = matchedRom;
  sources.value.push({
    url_cover: matchedRom.igdb_url_cover,
    name: "igdb",
  });
  sources.value.push({
    url_cover: matchedRom.moby_url_cover,
    name: "moby",
  });
}

function selectSource(source: matchedSource) {
  if (!selectedRom.value) return;
  updateRom(
    Object.assign(selectedRom.value, {
      url_cover: source.url_cover,
    })
  );
}

function toggleRenameAsSource() {
  renameAsSource.value = !renameAsSource.value;
}

function backToMatched() {
  showSelectSource.value = false;
  sources.value = [];
}

async function updateRom(selectedRom: SearchRomSchema) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  Object.assign(rom.value, selectedRom);

  await romApi
    .updateRom({ rom: rom.value, renameAsIGDB: renameAsSource.value })
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
  showSelectSource.value = false;
  sources.value = [];
}

onBeforeUnmount(() => {
  emitter?.off("showMatchRomDialog");
});
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-search-web"
    :loading-condition="searching"
    :empty-state-condition="matchedRoms.length == 0"
    empty-state-type="game"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="lgAndUp ? '90vh' : '775px'"
  >
    <template #header>
      <span class="ml-4">Filter:</span>
      <v-tooltip
        location="top"
        class="tooltip"
        transition="fade-transition"
        :text="
          heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED
            ? 'Filter IGDB matches'
            : 'IGDB source is not enabled'
        "
        open-delay="500"
        ><template #activator="{ props }">
          <v-avatar
            @click="toggleSourceFilter('igdb')"
            v-bind="props"
            class="ml-3 source-filter"
            :class="{
              filtered: isIGDBFiltered,
              disabled: !heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED,
            }"
            size="30"
            rounded="1"
          >
            <v-img src="/assets/scrappers/igdb.png" />
          </v-avatar>
        </template>
      </v-tooltip>
      <v-tooltip
        location="top"
        class="tooltip"
        transition="fade-transition"
        :text="
          heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED
            ? 'Filter Mobygames matches'
            : 'Mobygames source is not enabled'
        "
        open-delay="500"
        ><template #activator="{ props }">
          <v-avatar
            @click="toggleSourceFilter('moby')"
            v-bind="props"
            class="ml-3 source-filter"
            :class="{
              filtered: isMobyFiltered,
              disabled: !heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED,
            }"
            size="30"
            rounded="1"
          >
            <v-img src="/assets/scrappers/moby.png" /></v-avatar></template
      ></v-tooltip>
    </template>
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="6" sm="8">
          <v-text-field
            id="search-text-field"
            @keyup.enter="searchRom()"
            @click:clear="searchTerm = ''"
            class="bg-terciary"
            v-model="searchTerm"
            label="Search"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="4" sm="3">
          <v-select
            label="by"
            class="bg-terciary"
            :items="['ID', 'Name']"
            v-model="searchBy"
            hide-details
          />
        </v-col>
        <v-col>
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
    </template>
    <template #content>
      <v-row v-show="!showSelectSource" no-gutters>
        <v-col
          class="pa-1"
          cols="4"
          sm="3"
          md="2"
          v-show="!searching"
          v-for="matchedRom in filteredMatchedRoms"
        >
          <game-card
            @click="showSources(matchedRom)"
            :rom="matchedRom"
            title-on-footer
            transform-scale
            title-on-hover
          />
        </v-col>
      </v-row>
      <template v-if="showSelectSource">
        <v-row class="text-left" no-gutters>
          <v-col>
            <v-btn
              icon="mdi-arrow-left"
              rounded="0"
              variant="flat"
              size="small"
              @click="backToMatched"
            ></v-btn>
          </v-col>
        </v-row>
        <v-row no-gutters>
          <v-col cols="12">
            <v-row class="justify-center" no-gutters>
              <v-col
                :class="{
                  'source-cover-desktop': !xs,
                  'source-cover-mobile': xs,
                }"
                class="pa-1"
                v-for="source in sources"
              >
                <v-hover v-slot="{ isHovering, props }">
                  <v-card
                    v-bind="props"
                    class="transform-scale"
                    :class="{ 'on-hover': isHovering }"
                    :elevation="isHovering ? 20 : 3"
                    @click="selectSource(source)"
                  >
                    <v-img
                      :src="
                        !source.url_cover
                          ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                          : source.url_cover
                      "
                      :aspect-ratio="3 / 4"
                      lazy
                    >
                      <template #placeholder>
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
                      <v-row no-gutters class="text-white pa-1">
                        <v-avatar class="mr-1" size="30" rounded="1">
                          <v-img
                            :src="`/assets/scrappers/${source.name}.png`"
                          />
                        </v-avatar>
                      </v-row>
                    </v-img>
                  </v-card>
                </v-hover>
              </v-col>
            </v-row>
          </v-col>
          <v-col>
            <v-row class="mt-2 text-center" no-gutters>
              <v-col>
                <v-chip
                  @click="toggleRenameAsSource"
                  :variant="renameAsSource ? 'flat' : 'outlined'"
                  :color="renameAsSource ? 'romm-accent-1' : ''"
                  ><v-icon class="mr-1">{{
                    renameAsSource
                      ? "mdi-checkbox-outline"
                      : "mdi-checkbox-blank-outline"
                  }}</v-icon
                  >Rename file as source</v-chip
                >
              </v-col>
            </v-row>
            <v-row class="mt-2" no-gutters>
              <v-col>
                <v-card class="mx-auto bg-terciary">
                  <v-card-title class="text-center">
                    {{ selectedRom?.name }}
                  </v-card-title>
                  <v-card-text>
                    {{ selectedRom?.summary }}
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </template>
    </template>
    <template #footer>
      <v-row no-gutters class="text-center">
        <v-col>
          <v-chip variant="text">Results found:</v-chip>
          <v-chip size="small" class="ml-1 text-romm-accent-1" label>{{
            matchedRoms.length
          }}</v-chip>
        </v-col>
      </v-row>
    </template>
  </r-dialog>
</template>

<style scoped>
.source-filter {
  cursor: pointer;
  opacity: 0.4;
}
.source-filter.filtered {
  opacity: 1;
}
.source-filter.disabled {
  cursor: not-allowed !important;
  opacity: 0.4 !important;
}
.select-source-dialog {
  z-index: 9999 !important;
}
.source-cover-desktop {
  min-width: 220px;
  max-width: 220px;
}
.source-cover-mobile {
  min-width: 150px;
  max-width: 150px;
}
</style>