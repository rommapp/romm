<script setup lang="ts">
import ActionBar from "@/components/Details/ActionBar.vue";
import AdditionalContent from "@/components/Details/AdditionalContent.vue";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import FileInfo from "@/components/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Details/Info/GameInfo.vue";
import Personal from "@/components/Details/Personal.vue";
import RelatedGames from "@/components/Details/RelatedGames.vue";
import Saves from "@/components/Details/Saves.vue";
import States from "@/components/Details/States.vue";
import TitleInfo from "@/components/Details/Title.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeMount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import { useI18n } from "vue-i18n";
import VuePdfApp from "vue3-pdf-app";

const theme = useTheme();
const idConfig = {
  zoomIn: "zoomInId",
  zoomOut: "zoomOutId",
  toggleFindbar: "toggleFindbarId",
  download: "downloadId",
  firstPage: "firstPageId",
  nextPage: "nextPageId",
  previousPage: "previousPageId",
  lastPage: "lastPageId",
  sidebarToggle: "sidebarToggleId",
  numPages: "numPagesId",
  pageNumber: "pageNumberId",
};

// Props
const { t } = useI18n();
const route = useRoute();
const tab = ref<
  | "details"
  | "manual"
  | "saves"
  | "states"
  | "personal"
  | "additionalcontent"
  | "screenshots"
  | "relatedgames"
>("manual");
const { smAndDown, mdAndDown, mdAndUp, lgAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const noRomError = ref(false);
const romsStore = storeRoms();
const { currentRom, gettingRoms } = storeToRefs(romsStore);

async function fetchDetails() {
  gettingRoms.value = true;
  await romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then(({ data }) => {
      currentRom.value = data;
    })
    .catch((error) => {
      console.log(error);
      noRomError.value = true;
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      gettingRoms.value = false;
    });
}

onBeforeMount(async () => {
  const romId = parseInt(route.params.rom as string);

  // Only fetch details if the currentRom ID differs
  if (currentRom.value?.id !== romId) {
    emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
    await fetchDetails();
  } else {
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
  }

  const downloadStore = storeDownload();
  downloadStore.clear();
});

watch(
  () => route.fullPath,
  async () => {
    const romId = parseInt(route.params.rom as string);

    // Only fetch details if the currentRom ID differs
    if (currentRom.value?.id !== romId) {
      await fetchDetails();
    }
  },
);
</script>

<template>
  <template v-if="currentRom && !gettingRoms">
    <background-header />

    <v-row class="px-5" no-gutters :class="{ 'justify-center': smAndDown }">
      <v-col cols="auto">
        <v-container :width="270" id="artwork-container" class="pa-0">
          <game-card :key="currentRom.updated_at" :rom="currentRom" />
          <action-bar class="mt-2" :rom="currentRom" />
          <related-games v-if="mdAndUp" class="mt-4" :rom="currentRom" />
        </v-container>
      </v-col>

      <v-col>
        <div
          class="pl-4"
          :class="{ 'position-absolute title-desktop': mdAndUp }"
        >
          <title-info :rom="currentRom" />
        </div>
        <v-row
          :class="{ 'px-4': mdAndUp, 'justify-center': smAndDown }"
          no-gutters
        >
          <v-tabs
            v-model="tab"
            slider-color="primary"
            :class="{ 'mt-4': smAndDown }"
          >
            <v-tab value="details"> {{ t("rom.details") }} </v-tab>
            <v-tab value="manual" v-if="currentRom.has_manual">
              {{ t("rom.manual") }}
            </v-tab>
            <v-tab value="saves"> {{ t("common.saves") }} </v-tab>
            <v-tab value="states"> {{ t("common.states") }} </v-tab>
            <v-tab value="personal">
              {{ t("rom.personal") }}
            </v-tab>
            <v-tab
              v-if="
                mdAndDown &&
                ((currentRom.igdb_metadata?.expansions ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.dlcs ?? []).length > 0)
              "
              value="additionalcontent"
            >
              {{ t("rom.additional-content") }}
            </v-tab>
            <v-tab
              v-if="
                smAndDown &&
                ((currentRom.igdb_metadata?.remakes ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.remasters ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.expanded_games ?? []).length > 0)
              "
              value="relatedgames"
            >
              {{ t("rom.related-content") }}
            </v-tab>
          </v-tabs>
          <v-col cols="12" class="px-1">
            <v-window disabled v-model="tab" class="py-2">
              <v-window-item value="details">
                <v-row no-gutters>
                  <v-col>
                    <file-info :rom="currentRom" />
                    <game-info :rom="currentRom" />
                  </v-col>
                </v-row>
              </v-window-item>
              <v-window-item value="manual">
                <!-- TODO: extract pdf viewer to component -->
                <v-row no-gutters>
                  <v-col class="pa-2 bg-toplayer">
                    <button
                      class="ml-1"
                      :id="idConfig.sidebarToggle"
                      type="button"
                    >
                      <v-icon>mdi-menu</v-icon>
                    </button>
                    <input
                      class="ml-16 px-1"
                      style="width: 40px"
                      :id="idConfig.pageNumber"
                      type="number"
                    />
                    <span class="ml-2" :id="idConfig.numPages"></span>

                    <button
                      class="ml-8"
                      :id="idConfig.toggleFindbar"
                      type="button"
                    >
                      <v-icon>mdi-file-find-outline</v-icon>
                    </button>
                    <button class="ml-8" :id="idConfig.zoomIn" type="button">
                      <v-icon>mdi-magnify-plus-outline</v-icon>
                    </button>
                    <button class="ml-2" :id="idConfig.zoomOut" type="button">
                      <v-icon>mdi-magnify-minus-outline</v-icon>
                    </button>
                    <button class="ml-8" :id="idConfig.firstPage" type="button">
                      <v-icon>mdi-page-first</v-icon>
                    </button>
                    <button
                      class="ml-2"
                      :id="idConfig.previousPage"
                      type="button"
                    >
                      <v-icon>mdi-chevron-left</v-icon>
                    </button>
                    <button class="ml-2" :id="idConfig.nextPage" type="button">
                      <v-icon>mdi-chevron-right</v-icon>
                    </button>
                    <button class="ml-2" :id="idConfig.lastPage" type="button">
                      <v-icon>mdi-page-last</v-icon>
                    </button>
                    <button class="ml-8" :id="idConfig.download" type="button">
                      <v-icon>mdi-download</v-icon>
                    </button>
                  </v-col>
                </v-row>
                <vue-pdf-app
                  :id-config="idConfig"
                  :config="{ toolbar: false }"
                  :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
                  style="height: 100dvh"
                  :pdf="`/assets/romm/resources/${currentRom.path_manual}`"
                >
                </vue-pdf-app>
              </v-window-item>
              <v-window-item value="saves">
                <saves :rom="currentRom" />
              </v-window-item>
              <v-window-item value="states">
                <states :rom="currentRom" />
              </v-window-item>
              <v-window-item value="personal">
                <personal :rom="currentRom" />
              </v-window-item>
              <v-window-item
                v-if="
                  mdAndDown &&
                  (currentRom.igdb_metadata?.expansions ||
                    currentRom.igdb_metadata?.dlcs)
                "
                value="additionalcontent"
              >
                <additional-content :rom="currentRom" />
              </v-window-item>
              <!-- TODO: user screenshots -->
              <!-- <v-window-item v-if="rom.user_screenshots.lenght > 0" value="screenshots">
                <screenshots :rom="rom" />
              </v-window-item> -->
              <v-window-item
                v-if="
                  smAndDown &&
                  (currentRom.igdb_metadata?.remakes ||
                    currentRom.igdb_metadata?.remasters ||
                    currentRom.igdb_metadata?.expanded_games)
                "
                value="relatedgames"
              >
                <related-games :rom="currentRom" />
              </v-window-item>
            </v-window>
          </v-col>
        </v-row>
      </v-col>

      <v-col cols="auto" v-if="lgAndUp">
        <v-container :width="270" class="pa-0">
          <additional-content class="mt-2" :rom="currentRom" />
        </v-container>
      </v-col>
    </v-row>
  </template>

  <empty-game v-if="noRomError" />
</template>

<style scoped>
.title-desktop {
  margin-top: -190px;
}
#artwork-container {
  margin-top: -230px;
}
.pdf-app.light,
.pdf-app.dark {
  --pdf-app-background-color: rgba(var(--v-theme-surface)) !important;
}

/* Chrome, Safari, Edge, Opera */
input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Firefox */
input[type="number"] {
  -moz-appearance: textfield;
  text-align: right;
  padding-left: 1px;
  padding-right: 1px;
  border: 1px solid rgba(var(--v-theme-secondary));
  border-radius: 5px;
  -webkit-transition: 0.5s;
  transition: 0.5s;
  outline: none;
}
</style>
