<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import SelectSourceDialog from "@/components/Dialog/Rom/MatchRom/SelectSource.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import RDialog from "@/components/common/Dialog.vue";
import romApi from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";

const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const renameAsIGDB = ref(false);
const searching = ref(false);
const searchTerm = ref("");
const searchBy = ref("Name");
const searchExtended = ref(false);
const matchedRoms = ref<SearchRomSchema[]>([]);
const filteredMatchedRoms = ref<SearchRomSchema[]>();
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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-search-web"
    :loading-condition="searching"
    :empty-state-condition="matchedRoms.length == 0"
    empty-state-type="game"
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
          </v-avatar> </template
      ></v-tooltip>
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
        <v-col cols="5" md="6" lg="8">
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
        <v-col cols="3" md="2">
          <v-select
            label="by"
            class="bg-terciary"
            :items="['ID', 'Name']"
            v-model="searchBy"
            hide-details
          />
        </v-col>

        <v-col cols="2" lg="1">
          <v-tooltip
            location="top"
            class="tooltip"
            transition="fade-transition"
            text="Extended search to match by alternative names. This will take longer."
            open-delay="500"
            ><template #activator="{ props }">
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
        <v-col cols="2" lg="1">
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
      <v-row no-gutters>
        <v-col
          class="pa-1"
          cols="4"
          sm="3"
          md="2"
          v-show="!searching"
          v-for="matchedRom in filteredMatchedRoms"
        >
          <game-card
            @click="selectMatched(matchedRom)"
            :rom="matchedRom"
            title-on-footer
            transform-scale
          />
        </v-col>
      </v-row>
    </template>
    <template #footer>
      <v-checkbox
        v-model="renameAsIGDB"
        label="Rename rom"
        class="ml-3"
        hide-details
      />
    </template>
  </r-dialog>

  <select-source-dialog @select:source="updateRom" />
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
</style>
