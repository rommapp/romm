<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeMount, ref, watch, defineAsyncComponent } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import ActionBar from "@/components/Details/ActionBar.vue";
import AdditionalContent from "@/components/Details/AdditionalContent.vue";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import GameData from "@/components/Details/GameData.vue";
import HowLongToBeat from "@/components/Details/HowLongToBeat.vue";
import FileInfo from "@/components/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Details/Info/GameInfo.vue";
import Personal from "@/components/Details/Personal.vue";
import RelatedGames from "@/components/Details/RelatedGames.vue";
import TitleInfo from "@/components/Details/Title.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

// Dynamic import for PDFViewer
const PdfViewer = defineAsyncComponent(
  () => import("@/components/Details/PDFViewer.vue"),
);

const { t } = useI18n();
const route = useRoute();
const tab = ref<
  | "details"
  | "manual"
  | "gamedata"
  | "personal"
  | "timetobeat"
  | "additionalcontent"
  | "screenshots"
  | "relatedgames"
>("details");
const { smAndDown, mdAndDown, mdAndUp, lgAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const noRomError = ref(false);
const romsStore = storeRoms();
const platformsStore = storePlatforms();
const { currentRom, fetchingRoms } = storeToRefs(romsStore);

async function fetchDetails() {
  fetchingRoms.value = true;
  await romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then(({ data }) => {
      currentRom.value = data;
    })
    .catch((error) => {
      console.error(error);
      noRomError.value = true;
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      fetchingRoms.value = false;
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
    if (currentPlatform && currentPlatform != romsStore.currentPlatform) {
      romsStore.setCurrentPlatform(currentPlatform);
    }
    document.title = `${currentRom.value.name} | ${currentRom.value.platform_display_name}`;
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
  <template v-if="currentRom && !fetchingRoms">
    <BackgroundHeader />

    <v-row
      class="px-6 mb-6"
      no-gutters
      :class="{ 'justify-center': smAndDown }"
    >
      <v-col cols="auto">
        <v-container id="artwork-container" :width="270" class="pa-0">
          <GameCard
            :key="currentRom.updated_at"
            :rom="currentRom"
            :show-platform-icon="false"
            :show-action-bar="false"
          />
          <ActionBar :rom="currentRom" />
          <RelatedGames v-if="mdAndUp" class="mt-4" :rom="currentRom" />
        </v-container>
      </v-col>

      <v-col
        :md="
          !(
            lgAndUp &&
            (currentRom.igdb_metadata?.expansions?.length ||
              currentRom.igdb_metadata?.dlcs?.length)
          )
            ? 8
            : 7
        "
      >
        <div :class="{ 'position-absolute title-desktop pl-4': mdAndUp }">
          <TitleInfo :rom="currentRom" />
        </div>
        <v-row
          :class="{ 'px-4': mdAndUp, 'justify-center': smAndDown }"
          no-gutters
        >
          <v-tabs
            v-model="tab"
            slider-color="primary"
            show-arrows
            :class="{ 'mt-4': smAndDown }"
          >
            <v-tab value="details">
              {{ t("rom.details") }}
            </v-tab>
            <v-tab v-if="currentRom.has_manual" value="manual">
              {{ t("rom.manual") }}
            </v-tab>
            <v-tab value="gamedata"> Game data </v-tab>
            <v-tab value="personal">
              {{ t("rom.personal") }}
            </v-tab>
            <v-tab v-if="currentRom.hltb_id" value="timetobeat">
              {{ t("rom.how-long-to-beat") }}
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
            <v-window v-model="tab" disabled class="py-2">
              <v-window-item value="details">
                <v-row no-gutters>
                  <v-col>
                    <FileInfo :rom="currentRom" />
                    <GameInfo :rom="currentRom" />
                  </v-col>
                </v-row>
              </v-window-item>
              <v-window-item value="manual">
                <PdfViewer v-if="currentRom.has_manual" :rom="currentRom" />
              </v-window-item>
              <v-window-item value="gamedata">
                <GameData :rom="currentRom" />
              </v-window-item>
              <v-window-item value="personal">
                <Personal :rom="currentRom" />
              </v-window-item>
              <v-window-item v-if="currentRom.hltb_metadata" value="timetobeat">
                <HowLongToBeat :rom="currentRom" />
              </v-window-item>
              <v-window-item
                v-if="
                  mdAndDown &&
                  (currentRom.igdb_metadata?.expansions ||
                    currentRom.igdb_metadata?.dlcs)
                "
                value="additionalcontent"
              >
                <AdditionalContent :rom="currentRom" />
              </v-window-item>
              <v-window-item
                v-if="
                  smAndDown &&
                  (currentRom.igdb_metadata?.remakes ||
                    currentRom.igdb_metadata?.remasters ||
                    currentRom.igdb_metadata?.expanded_games)
                "
                value="relatedgames"
              >
                <RelatedGames :rom="currentRom" />
              </v-window-item>
            </v-window>
          </v-col>
        </v-row>
      </v-col>

      <v-col
        v-if="
          lgAndUp &&
          (currentRom.igdb_metadata?.expansions?.length ||
            currentRom.igdb_metadata?.dlcs?.length)
        "
        cols="auto"
      >
        <v-container width="270px" class="pa-0">
          <AdditionalContent class="mt-2" :rom="currentRom" />
        </v-container>
      </v-col>
    </v-row>
  </template>

  <EmptyGame v-if="noRomError" />
</template>

<style scoped>
.title-desktop {
  margin-top: -190px;
}

#artwork-container {
  margin-top: -230px;
}
</style>
