<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import EmptyManualMatch from "@/components/common/EmptyStates/EmptyManualMatch.vue";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { getMissingCoverImage } from "@/utils/covers";

type MatchedSource = {
  url_cover: string | undefined;
  name: "IGDB" | "Mobygames" | "Screenscraper";
  logo_path: string;
};

// Props
const { t } = useI18n();
const { xs, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const galleryViewStore = storeGalleryView();
const platfotmsStore = storePlatforms();
const searching = ref(false);
const route = useRoute();
const searchText = ref("");
const searchBy = ref("Name");
const searched = ref(false);
const matchedRoms = ref<SearchRomSchema[]>([]);
const filteredMatchedRoms = ref<SearchRomSchema[]>();
const emitter = inject<Emitter<Events>>("emitter");
const showSelectSource = ref(false);
const renameFromSource = ref(false);
const selectedMatchRom = ref<SearchRomSchema>();
const selectedCover = ref<MatchedSource>();
const sources = ref<MatchedSource[]>([]);
const heartbeat = storeHeartbeat();
const isIGDBFiltered = ref(true);
const isMobyFiltered = ref(true);
const isSSFiltered = ref(true);
const computedAspectRatio = computed(() => {
  const ratio =
    platfotmsStore.getAspectRatio(rom.value?.platform_id ?? -1) ||
    galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
});
emitter?.on("showMatchRomDialog", (romToSearch) => {
  rom.value = romToSearch;
  show.value = true;
  matchedRoms.value = [];

  // Use name as search term, only when it's matched
  // Otherwise use the filename without tags and extensions
  searchText.value =
    romToSearch.igdb_id || romToSearch.moby_id || romToSearch.ss_id
      ? (romToSearch.name ?? "")
      : romToSearch.fs_name_no_tags;
});
const missingCoverImage = computed(() =>
  getMissingCoverImage(rom.value?.name || rom.value?.fs_name || ""),
);

// Functions
function toggleSourceFilter(source: MatchedSource["name"]) {
  if (source == "IGDB" && heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED) {
    isIGDBFiltered.value = !isIGDBFiltered.value;
  } else if (
    source == "Mobygames" &&
    heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED
  ) {
    isMobyFiltered.value = !isMobyFiltered.value;
  } else if (
    source == "Screenscraper" &&
    heartbeat.value.METADATA_SOURCES.SS_API_ENABLED
  ) {
    isSSFiltered.value = !isSSFiltered.value;
  }
  filteredMatchedRoms.value = matchedRoms.value.filter((rom) => {
    if (
      (rom.igdb_id && isIGDBFiltered.value) ||
      (rom.moby_id && isMobyFiltered.value) ||
      (rom.ss_id && isSSFiltered.value)
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
        searchTerm: searchText.value,
        searchBy: searchBy.value,
      })
      .then((response) => {
        matchedRoms.value = response.data;
        filteredMatchedRoms.value = matchedRoms.value.filter((rom) => {
          if (
            (rom.igdb_id && isIGDBFiltered.value) ||
            (rom.moby_id && isMobyFiltered.value) ||
            (rom.ss_id && isSSFiltered.value)
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
        searched.value = true;
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
  selectedMatchRom.value = matchedRom;
  sources.value = [];
  if (matchedRom.igdb_url_cover || matchedRom.igdb_id) {
    sources.value.push({
      url_cover: matchedRom.igdb_url_cover,
      name: "IGDB",
      logo_path: "/assets/scrappers/igdb.png",
    });
  }
  if (matchedRom.moby_url_cover || matchedRom.moby_id) {
    sources.value.push({
      url_cover: matchedRom.moby_url_cover,
      name: "Mobygames",
      logo_path: "/assets/scrappers/moby.png",
    });
  }
  if (matchedRom.ss_url_cover || matchedRom.ss_id) {
    sources.value.push({
      url_cover: matchedRom.ss_url_cover,
      name: "Screenscraper",
      logo_path: "/assets/scrappers/ss.png",
    });
  }
  if (sources.value.length == 1) {
    selectedCover.value = sources.value[0];
  }
}

function selectCover(source: MatchedSource) {
  selectedCover.value = source;
}

function confirm() {
  if (!selectedMatchRom.value || !selectedCover.value) return;
  updateRom(selectedMatchRom.value, selectedCover.value.url_cover);
  closeDialog();
}

function toggleRenameAsSource() {
  renameFromSource.value = !renameFromSource.value;
}

function backToMatched() {
  showSelectSource.value = false;
  selectedCover.value = undefined;
  selectedMatchRom.value = undefined;
  sources.value = [];
  renameFromSource.value = false;
}

async function updateRom(
  selectedRom: SearchRomSchema,
  urlCover: string | undefined,
) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  // Set the properties from the selected rom
  rom.value = {
    ...rom.value,
    fs_name:
      renameFromSource.value && selectedMatchRom.value
        ? rom.value.fs_name.replace(
            rom.value.fs_name_no_ext,
            selectedMatchRom.value.name,
          )
        : rom.value.fs_name,
    igdb_id: selectedRom.igdb_id || null,
    moby_id: selectedRom.moby_id || null,
    ss_id: selectedRom.ss_id || null,
    name: selectedRom.name || null,
    slug: selectedRom.slug || null,
    summary: selectedRom.summary || null,
    url_cover:
      urlCover ||
      selectedRom.igdb_url_cover ||
      selectedRom.ss_url_cover ||
      selectedRom.moby_url_cover ||
      null,
  };

  // Replace the cover image with a higher resolution
  if (rom.value.url_cover) {
    rom.value.url_cover = rom.value.url_cover.replace("t_cover_big", "t_1080p");
  }

  await romApi
    .updateRom({ rom: rom.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Rom updated successfully!",
        icon: "mdi-check-bold",
        color: "green",
      });
      romsStore.update(data as SimpleRom);
      if (route.name == "rom") {
        romsStore.currentRom = data;
      }
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
  searching.value = false;
  searched.value = false;
  searchBy.value = "Name";
  sources.value = [];
  showSelectSource.value = false;
  selectedCover.value = undefined;
  selectedMatchRom.value = undefined;
  renameFromSource.value = false;
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
    :empty-state-type="searched ? 'game' : undefined"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="lgAndUp ? '90vh' : '775px'"
  >
    <template #header>
      <span class="ml-4">{{ t("common.filter") }}:</span>
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
            @click="toggleSourceFilter('IGDB')"
            v-bind="props"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isIGDBFiltered &&
                heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED,
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
            @click="toggleSourceFilter('Mobygames')"
            v-bind="props"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isMobyFiltered &&
                heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED,
            }"
            size="30"
            rounded="1"
          >
            <v-img src="/assets/scrappers/moby.png" /></v-avatar></template
      ></v-tooltip>
      <v-tooltip
        location="top"
        class="tooltip"
        transition="fade-transition"
        :text="
          heartbeat.value.METADATA_SOURCES.SS_API_ENABLED
            ? 'Filter Screenscraper matches'
            : 'Screenscraper source is not enabled'
        "
        open-delay="500"
        ><template #activator="{ props }">
          <v-avatar
            @click="toggleSourceFilter('Screenscraper')"
            v-bind="props"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isSSFiltered && heartbeat.value.METADATA_SOURCES.SS_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.SS_API_ENABLED,
            }"
            size="30"
            rounded="1"
          >
            <v-img src="/assets/scrappers/ss.png" />
          </v-avatar>
        </template>
      </v-tooltip>
    </template>
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="6" sm="8">
          <v-text-field
            autofocus
            id="search-text-field"
            @keyup.enter="searchRom()"
            @click:clear="searchText = ''"
            class="bg-toplayer"
            v-model="searchText"
            :disabled="searching"
            :label="t('common.search')"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="4" sm="3">
          <v-select
            :disabled="searching"
            :label="t('rom.by')"
            class="bg-toplayer"
            :items="['ID', 'Name']"
            v-model="searchBy"
            hide-details
          />
        </v-col>
        <v-col>
          <v-btn
            type="submit"
            @click="searchRom()"
            class="bg-toplayer"
            variant="text"
            rounded="0"
            icon="mdi-search-web"
            block
            :disabled="searching"
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-row class="align-content-start" v-show="!showSelectSource" no-gutters>
        <v-col
          class="pa-1"
          cols="4"
          sm="3"
          md="2"
          v-show="!searching"
          v-for="matchedRom in filteredMatchedRoms"
        >
          <game-card
            v-if="rom"
            @click="showSources(matchedRom)"
            :rom="matchedRom"
            transformScale
            titleOnHover
            pointerOnHover
            disableViewTransition
          />
        </v-col>
      </v-row>
      <template v-if="showSelectSource">
        <v-row no-gutters>
          <v-col cols="12">
            <v-card class="mx-auto bg-toplayer">
              <v-card-title class="text-center">
                <v-btn
                  color="toplayer"
                  icon="mdi-arrow-left"
                  variant="flat"
                  size="small"
                  @click="backToMatched"
                  style="float: left"
                />
                {{ selectedMatchRom?.name }}
              </v-card-title>
              <v-card-text class="text-subtitle-2">
                {{ selectedMatchRom?.summary }}
              </v-card-text>
            </v-card>
          </v-col>
          <v-col v-if="sources.length > 1" cols="12">
            <v-row no-gutters class="mt-4 justify-center text-center">
              <v-col>
                <span class="text-body-1">{{
                  t("rom.select-cover-image")
                }}</span>
              </v-col>
            </v-row>
          </v-col>
          <v-col cols="12">
            <v-row class="justify-center mt-4" no-gutters>
              <v-col class="pa-1" cols="auto" v-for="source in sources">
                <v-hover v-slot="{ isHovering, props }">
                  <v-card
                    :width="xs ? 150 : 220"
                    v-bind="props"
                    class="transform-scale mx-2"
                    :class="{
                      'on-hover': isHovering,
                      'border-primary': selectedCover?.name == source.name,
                    }"
                    :elevation="isHovering ? 20 : 3"
                    @click="selectCover(source)"
                  >
                    <v-img
                      :src="source.url_cover || missingCoverImage"
                      :aspect-ratio="computedAspectRatio"
                      cover
                      lazy
                    >
                      <template #placeholder>
                        <div
                          class="d-flex align-center justify-center fill-height"
                        >
                          <v-progress-circular
                            color="primary"
                            :width="2"
                            indeterminate
                          />
                        </div>
                      </template>
                      <v-row no-gutters class="text-white pa-1">
                        <v-avatar class="mr-1" size="30" rounded="1">
                          <v-img :src="source.logo_path" />
                        </v-avatar>
                      </v-row>
                      <template #error>
                        <v-img :src="missingCoverImage" />
                      </template>
                    </v-img>
                  </v-card>
                </v-hover>
              </v-col>
            </v-row>
          </v-col>
          <v-col cols="12" v-if="selectedMatchRom">
            <v-row class="mt-4 text-center" no-gutters>
              <v-col>
                <v-chip
                  @click="toggleRenameAsSource"
                  variant="text"
                  :disabled="selectedCover == undefined"
                  ><v-icon
                    :color="renameFromSource ? 'primary' : ''"
                    class="mr-1"
                    >{{
                      selectedCover && renameFromSource
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}</v-icon
                  >{{
                    t("rom.rename-file-part1", { source: selectedCover?.name })
                  }}</v-chip
                >
                <v-list-item v-if="rom && renameFromSource" class="mt-2">
                  <span>{{ t("rom.rename-file-part2") }}</span>
                  <br />
                  <span>{{ t("rom.rename-file-part3") }}</span
                  ><span class="text-primary ml-1">{{ rom.fs_name }}</span>
                  <br />
                  <span class="mx-1">{{ t("rom.rename-file-part4") }}</span
                  ><span class="text-secondary">{{
                    rom.fs_name.replace(
                      rom.fs_name_no_ext,
                      selectedMatchRom.name,
                    )
                  }}</span>
                  <br />
                  <span class="text-caption font-italic font-weight-bold"
                    >*{{ t("rom.rename-file-part5") }}</span
                  >
                </v-list-item>
              </v-col>
            </v-row>
          </v-col>
          <v-col cols="12">
            <v-row no-gutters class="my-4 justify-center">
              <v-btn-group divided density="compact">
                <v-btn class="bg-toplayer" @click="backToMatched">
                  {{ t("common.cancel") }}
                </v-btn>
                <v-btn
                  class="text-romm-green bg-toplayer"
                  :disabled="selectedCover == undefined"
                  :variant="selectedCover == undefined ? 'plain' : 'flat'"
                  @click="confirm"
                >
                  {{ t("common.confirm") }}
                </v-btn>
              </v-btn-group>
            </v-row>
          </v-col>
        </v-row>
      </template>
    </template>
    <template #empty-state>
      <empty-manual-match />
    </template>
    <template #footer>
      <v-row no-gutters class="text-center">
        <v-col>
          <v-chip label class="pr-0" size="small"
            >{{ t("rom.results-found") }}:<v-chip
              color="primary"
              class="ml-2 px-2"
              label
              >{{ !searching ? matchedRoms.length : ""
              }}<v-progress-circular
                v-if="searching"
                :width="1"
                :size="10"
                color="primary"
                indeterminate
            /></v-chip>
          </v-chip>
        </v-col>
      </v-row>
    </template>
  </r-dialog>
</template>
