<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import EmptyManualMatch from "@/components/common/EmptyStates/EmptyManualMatch.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom, type SearchRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getMissingCoverImage } from "@/utils/covers";

type MatchedSource = {
  url_cover: string | undefined;
  name:
    | "IGDB"
    | "Mobygames"
    | "Screenscraper"
    | "Flashpoint"
    | "Launchbox"
    | "SteamGridDB";
  logo_path: string;
};

const { t } = useI18n();
const { xs, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const galleryViewStore = storeGalleryView();
const searching = ref(false);
const route = useRoute();
const searchText = ref("");
const searchBy = ref("Name");
const searched = ref(false);
const matchedRoms = ref<SearchRom[]>([]);
const filteredMatchedRoms = ref<SearchRom[]>();
const emitter = inject<Emitter<Events>>("emitter");
const showSelectSource = ref(false);
const renameFromSource = ref(false);
const selectedMatchRom = ref<SearchRom>();
const selectedCover = ref<MatchedSource>();
const sources = ref<MatchedSource[]>([]);
const heartbeat = storeHeartbeat();
const isIGDBFiltered = ref(true);
const isMobyFiltered = ref(true);
const isSSFiltered = ref(true);
const isFlashpointFiltered = ref(true);
const isLaunchboxFiltered = ref(true);

const computedAspectRatio = computed(() => {
  return galleryViewStore.getAspectRatio({
    platformId: rom.value?.platform_id,
    boxartStyle: "cover_path",
  });
});

const handleShowMatchRomDialog = (romToSearch: SimpleRom) => {
  rom.value = romToSearch;
  show.value = true;
  matchedRoms.value = [];
  searchText.value = romToSearch.is_identified
    ? (romToSearch.name ?? "")
    : romToSearch.fs_name_no_tags;
};
emitter?.on("showMatchRomDialog", handleShowMatchRomDialog);

const missingCoverImage = computed(() =>
  getMissingCoverImage(rom.value?.name || rom.value?.fs_name || ""),
);

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
  } else if (
    source == "Flashpoint" &&
    heartbeat.value.METADATA_SOURCES.FLASHPOINT_API_ENABLED
  ) {
    isFlashpointFiltered.value = !isFlashpointFiltered.value;
  } else if (
    source == "Launchbox" &&
    heartbeat.value.METADATA_SOURCES.LAUNCHBOX_API_ENABLED
  ) {
    isLaunchboxFiltered.value = !isLaunchboxFiltered.value;
  }

  filteredMatchedRoms.value = matchedRoms.value.filter((rom) => {
    if (
      (rom.igdb_id && isIGDBFiltered.value) ||
      (rom.moby_id && isMobyFiltered.value) ||
      (rom.ss_id && isSSFiltered.value) ||
      (rom.flashpoint_id && isFlashpointFiltered.value) ||
      (rom.launchbox_id && isLaunchboxFiltered.value)
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
            (rom.ss_id && isSSFiltered.value) ||
            (rom.flashpoint_id && isFlashpointFiltered.value) ||
            (rom.launchbox_id && isLaunchboxFiltered.value)
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

function showSources(matchedRom: SearchRom) {
  if (!rom.value) return;

  var cardContent = document.getElementById("r-dialog-content");
  if (cardContent) {
    cardContent.scrollTop = 0;
  }
  showSelectSource.value = true;
  selectedMatchRom.value = matchedRom;
  sources.value = [];
  if (matchedRom.igdb_url_cover) {
    sources.value.push({
      url_cover: matchedRom.igdb_url_cover,
      name: "IGDB",
      logo_path: "/assets/scrappers/igdb.png",
    });
  }
  if (matchedRom.moby_url_cover) {
    sources.value.push({
      url_cover: matchedRom.moby_url_cover,
      name: "Mobygames",
      logo_path: "/assets/scrappers/moby.png",
    });
  }
  if (matchedRom.ss_url_cover) {
    sources.value.push({
      url_cover: matchedRom.ss_url_cover,
      name: "Screenscraper",
      logo_path: "/assets/scrappers/ss.png",
    });
  }
  if (matchedRom.sgdb_url_cover) {
    sources.value.push({
      url_cover: matchedRom.sgdb_url_cover,
      name: "SteamGridDB",
      logo_path: "/assets/scrappers/sgdb.png",
    });
  }
  if (matchedRom.flashpoint_url_cover) {
    sources.value.push({
      url_cover: matchedRom.flashpoint_url_cover,
      name: "Flashpoint",
      logo_path: "/assets/scrappers/flashpoint.png",
    });
  }
  if (matchedRom.launchbox_url_cover) {
    sources.value.push({
      url_cover: matchedRom.launchbox_url_cover,
      name: "Launchbox",
      logo_path: "/assets/scrappers/launchbox.png",
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
  if (!selectedMatchRom.value) return;
  updateRom(selectedMatchRom.value, selectedCover.value?.url_cover);
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

async function updateRom(selectedRom: SearchRom, urlCover: string | undefined) {
  if (!rom.value) return;

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  // Set the properties from the selected rom
  rom.value = {
    ...rom.value,
    fs_name:
      renameFromSource.value && selectedMatchRom.value
        ? rom.value.fs_name.replace(
            rom.value.fs_name_no_tags,
            selectedMatchRom.value.name,
          )
        : rom.value.fs_name,
    igdb_id: selectedRom.igdb_id || null,
    ss_id: selectedRom.ss_id || null,
    moby_id: selectedRom.moby_id || null,
    flashpoint_id: selectedRom.flashpoint_id || null,
    launchbox_id: selectedRom.launchbox_id || null,
    name: selectedRom.name || null,
    slug: selectedRom.slug || null,
    summary: selectedRom.summary || null,
    url_cover:
      urlCover ||
      selectedRom.igdb_url_cover ||
      selectedRom.ss_url_cover ||
      selectedRom.moby_url_cover ||
      selectedRom.flashpoint_url_cover ||
      selectedRom.launchbox_url_cover ||
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
  emitter?.off("showMatchRomDialog", handleShowMatchRomDialog);
});
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-search-web"
    :loading-condition="searching"
    :empty-state-condition="matchedRoms.length == 0"
    :empty-state-type="searched ? 'game' : undefined"
    scroll-content
    :width="lgAndUp ? '60vw' : '95vw'"
    :height="xs ? '80vh' : '90vh'"
    @close="closeDialog"
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
      >
        <template #activator="{ props }">
          <v-avatar
            v-bind="props"
            variant="text"
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
            @click="toggleSourceFilter('IGDB')"
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
      >
        <template #activator="{ props }">
          <v-avatar
            v-bind="props"
            variant="text"
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
            @click="toggleSourceFilter('Mobygames')"
          >
            <v-img src="/assets/scrappers/moby.png" />
          </v-avatar>
        </template>
      </v-tooltip>
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
      >
        <template #activator="{ props }">
          <v-avatar
            v-bind="props"
            variant="text"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isSSFiltered && heartbeat.value.METADATA_SOURCES.SS_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.SS_API_ENABLED,
            }"
            size="30"
            rounded="1"
            @click="toggleSourceFilter('Screenscraper')"
          >
            <v-img src="/assets/scrappers/ss.png" />
          </v-avatar>
        </template>
      </v-tooltip>
      <v-tooltip
        location="top"
        class="tooltip"
        transition="fade-transition"
        :text="
          heartbeat.value.METADATA_SOURCES.LAUNCHBOX_API_ENABLED
            ? 'Filter Launchbox matches'
            : 'Launchbox source is not enabled'
        "
        open-delay="500"
      >
        <template #activator="{ props }">
          <v-avatar
            v-bind="props"
            variant="text"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isLaunchboxFiltered &&
                heartbeat.value.METADATA_SOURCES.LAUNCHBOX_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.LAUNCHBOX_API_ENABLED,
            }"
            size="30"
            rounded="1"
            @click="toggleSourceFilter('Launchbox')"
          >
            <v-img src="/assets/scrappers/launchbox.png" />
          </v-avatar>
        </template>
      </v-tooltip>
      <v-tooltip
        location="top"
        class="tooltip"
        transition="fade-transition"
        :text="
          heartbeat.value.METADATA_SOURCES.FLASHPOINT_API_ENABLED
            ? 'Filter Flashpoint matches'
            : 'Flashpoint source is not enabled'
        "
        open-delay="500"
      >
        <template #activator="{ props }">
          <v-avatar
            v-bind="props"
            variant="text"
            class="ml-3 cursor-pointer opacity-40"
            :class="{
              'opacity-100':
                isFlashpointFiltered &&
                heartbeat.value.METADATA_SOURCES.FLASHPOINT_API_ENABLED,
              'cursor-not-allowed':
                !heartbeat.value.METADATA_SOURCES.FLASHPOINT_API_ENABLED,
            }"
            size="30"
            rounded="1"
            @click="toggleSourceFilter('Flashpoint')"
          >
            <v-img src="/assets/scrappers/flashpoint.png" />
          </v-avatar>
        </template>
      </v-tooltip>
      <v-chip label class="ml-4 pr-0" size="small">
        {{ t("rom.results-found") }}:
        <v-chip color="primary" class="ml-2 px-2" label>
          {{ !searching ? matchedRoms.length : "" }}
          <v-progress-circular
            v-if="searching"
            :width="1"
            :size="10"
            color="primary"
            indeterminate
          />
        </v-chip>
      </v-chip>
    </template>
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="6" sm="8">
          <v-text-field
            id="search-text-field"
            v-model="searchText"
            class="bg-toplayer"
            :disabled="searching"
            :label="t('common.search')"
            hide-details
            clearable
            @keyup.enter="searchRom"
            @click:clear="searchText = ''"
          />
        </v-col>
        <v-col cols="4" sm="3">
          <v-select
            v-model="searchBy"
            :disabled="searching"
            :label="t('rom.by')"
            class="bg-toplayer"
            :items="['ID', 'Name']"
            hide-details
          />
        </v-col>
        <v-col>
          <v-btn
            type="submit"
            class="bg-toplayer"
            variant="text"
            rounded="0"
            icon="mdi-search-web"
            block
            :disabled="searching"
            @click="searchRom"
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <template v-if="!showSelectSource">
        <v-row class="align-content-start" no-gutters>
          <v-col
            v-for="matchedRom in filteredMatchedRoms"
            v-show="!searching"
            :key="matchedRom.name"
            class="pa-1"
            cols="4"
            sm="3"
            md="2"
          >
            <GameCard
              v-if="rom"
              :rom="matchedRom"
              transform-scale
              title-on-hover
              pointer-on-hover
              disable-view-transition
              :show-action-bar="false"
              force-boxart="cover_path"
              @click="showSources(matchedRom)"
            />
          </v-col>
        </v-row>
      </template>
      <template v-else>
        <v-row no-gutters>
          <v-col cols="12">
            <v-card class="mx-auto bg-toplayer">
              <v-card-title class="text-center">
                <v-btn
                  color="toplayer"
                  icon="mdi-arrow-left"
                  variant="flat"
                  size="small"
                  style="float: left"
                  @click="backToMatched"
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
              <v-col
                v-for="source in sources"
                :key="source.name"
                class="pa-1"
                cols="auto"
              >
                <GameCard
                  :rom="{
                    id: 0,
                    name: source.name,
                    platform_id: selectedMatchRom?.platform_id || 0,
                    is_identified: true,
                    is_unidentified: false,
                  }"
                  :cover-src="source.url_cover"
                  :width="xs ? 150 : 220"
                  transform-scale
                  pointer-on-hover
                  disable-view-transition
                  force-boxart="cover_path"
                  :show-action-bar="false"
                  :with-border-primary="selectedCover?.name == source.name"
                  @click="selectCover(source)"
                >
                  <template #append-inner-right>
                    <v-avatar class="mr-1 mb-1" size="30" rounded="1">
                      <v-img :src="source.logo_path" />
                    </v-avatar>
                  </template>
                </GameCard>
              </v-col>
            </v-row>
          </v-col>
          <v-col v-if="selectedMatchRom" cols="12">
            <v-row class="mt-4 text-center" no-gutters>
              <v-col>
                <v-chip
                  variant="text"
                  :disabled="selectedCover == undefined"
                  @click="toggleRenameAsSource"
                >
                  <v-icon
                    :color="renameFromSource ? 'primary' : ''"
                    class="mr-1"
                  >
                    {{
                      selectedCover && renameFromSource
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}
                  </v-icon>
                  {{
                    t("rom.rename-file-title", { source: selectedCover?.name })
                  }}
                </v-chip>
                <v-list-item v-if="rom && renameFromSource" class="mt-2">
                  <span>{{
                    t("rom.rename-file-details", {
                      from: rom.fs_name,
                      to: rom.fs_name.replace(
                        rom.fs_name_no_tags,
                        selectedMatchRom.name,
                      ),
                    })
                  }}</span>
                </v-list-item>
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </template>
    </template>
    <template #empty-state>
      <EmptyManualMatch />
    </template>
    <template #footer>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="text-romm-green bg-toplayer"
            variant="flat"
            @click="confirm"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
