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
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeMount, ref, watch, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
// Dynamic import for PDFViewer
const PdfViewer = defineAsyncComponent(
  () => import("@/components/Details/PDFViewer.vue"),
);

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
>("details");
const { smAndDown, mdAndDown, mdAndUp, lgAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const noRomError = ref(false);
const romsStore = storeRoms();
const platformsStore = storePlatforms();
const { currentRom, gettingRoms } = storeToRefs(romsStore);

// Functions
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

  if (currentRom.value) {
    const currentPlatform = platformsStore.get(currentRom.value.platform_id);
    if (currentPlatform) romsStore.setCurrentPlatform(currentPlatform);
  }

  const downloadStore = storeDownload();
  downloadStore.reset();
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
                <pdf-viewer v-if="currentRom.has_manual" :rom="currentRom" />
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
</style>
