<script setup lang="ts">
import ActionBar from "@/components/Details/ActionBar.vue";
import AdditionalContent from "@/components/Details/AdditionalContent.vue";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import FileInfo from "@/components/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Details/Info/GameInfo.vue";
import Notes from "@/components/Details/Notes.vue";
import RelatedGames from "@/components/Details/RelatedGames.vue";
import Saves from "@/components/Details/Saves.vue";
import States from "@/components/Details/States.vue";
import TitleInfo from "@/components/Details/Title.vue";
import EmptyGame from "@/components/common/EmptyGame.vue";
import Cover from "@/components/common/Game/Card/Base.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import type { Platform } from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeMount, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const route = useRoute();
const platform = ref<Platform>();
const tab = ref<
  | "details"
  | "saves"
  | "states"
  | "notes"
  | "additionalcontent"
  | "screenshots"
  | "relatedgames"
>("details");
const { smAndDown, mdAndDown, mdAndUp, lgAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const noRomError = ref(false);
const romsStore = storeRoms();
const { currentRom } = storeToRefs(romsStore);

// Functions
async function fetchDetails() {
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
    });

  if (!noRomError.value) {
    await platformApi
      .getPlatform(currentRom.value?.platform_id)
      .then((response) => {
        platform.value = response.data;
      })
      .catch((error) => {
        console.log(error);
      })
      .finally(() => {
        emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }
}

onBeforeMount(async () => {
  emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
  if (currentRom.value?.id == parseInt(route.params.rom as string)) {
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
  } else {
    await fetchDetails();
  }
  const downloadStore = storeDownload();
  downloadStore.clear();
});

onBeforeRouteLeave(() => {
  currentRom.value = null;
});

watch(
  () => route.fullPath,
  async () => {
    await fetchDetails();
  }
);
</script>

<template>
  <!-- TODO: review layout on certain roms - ej: mortal kombat 2 for gb  -->
  <template v-if="currentRom && platform">
    <background-header />

    <v-row
      class="px-5"
      :class="{
        'ml-6': mdAndUp,
        'justify-center': smAndDown,
      }"
      no-gutters
    >
      <v-col
        class="cover"
        :class="{
          'cover-desktop': mdAndUp,
          'cover-mobile': smAndDown,
        }"
      >
        <cover
          :key="currentRom.updated_at"
          :pointerOnHover="false"
          :rom="currentRom"
        />
        <action-bar class="mt-2" :rom="currentRom" />
        <related-games v-if="mdAndUp" class="mt-3" :rom="currentRom" />
      </v-col>

      <v-col
        cols="12"
        md="8"
        class="px-5"
        :class="{
          'info-lg': mdAndUp,
          'info-mobile': smAndDown,
        }"
      >
        <div
          class="px-3 pb-3"
          :class="{
            'position-absolute title-desktop': mdAndUp,
            'justify-center': smAndDown,
          }"
        >
          <title-info :rom="currentRom" :platform="platform" />
        </div>
        <v-row
          :class="{
            'justify-center': smAndDown,
          }"
          no-gutters
        >
          <v-tabs v-model="tab" slider-color="romm-accent-1" rounded="0">
            <v-tab value="details" rounded="0"> Details </v-tab>
            <v-tab value="saves" rounded="0"> Saves </v-tab>
            <v-tab value="states" rounded="0"> States </v-tab>
            <v-tab value="notes" rounded="0"> Notes </v-tab>
            <v-tab
              v-if="
                mdAndDown &&
                ((currentRom.igdb_metadata?.expansions ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.dlcs ?? []).length > 0)
              "
              value="additionalcontent"
              rounded="0"
            >
              Additional content
            </v-tab>
            <!-- TODO: user screenshots -->
            <!-- <v-tab value="screenshots" rounded="0">Screenshots</v-tab> -->
            <v-tab
              v-if="
                smAndDown &&
                ((currentRom.igdb_metadata?.remakes ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.remasters ?? []).length > 0 ||
                  (currentRom.igdb_metadata?.expanded_games ?? []).length > 0)
              "
              value="relatedgames"
              rounded="0"
            >
              Related Games
            </v-tab>
          </v-tabs>
        </v-row>
        <v-row no-gutters class="mb-4">
          <v-col cols="12">
            <v-window disabled v-model="tab" class="py-2">
              <v-window-item value="details">
                <v-row no-gutters :class="{ 'mx-2': mdAndUp }">
                  <v-col>
                    <file-info :rom="currentRom" :platform="platform" />
                    <game-info :rom="currentRom" />
                  </v-col>
                </v-row>
              </v-window-item>
              <v-window-item value="saves">
                <saves :rom="currentRom" />
              </v-window-item>
              <v-window-item value="states">
                <states :rom="currentRom" />
              </v-window-item>
              <v-window-item value="notes">
                <notes :rom="currentRom" />
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

      <template v-if="lgAndUp">
        <v-col>
          <additional-content :rom="currentRom" />
        </v-col>
      </template>
    </v-row>
  </template>

  <empty-game v-if="noRomError" />
</template>

<style scoped>
.cover {
  min-width: 270px;
  min-height: 360px;
  max-width: 270px;
  max-height: 360px;
}
.cover-desktop {
  margin-top: -230px;
}
.title-desktop {
  margin-top: -190px;
  margin-left: -20px;
}
.cover-mobile {
  margin-top: -280px;
}
.info-mobile {
  margin-top: 100px;
}
</style>
