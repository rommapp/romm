<script setup lang="ts">
import type { PlatformSchema } from "@/__generated__";
import ActionBar from "@/components/Details/ActionBar.vue";
import AdditionalContent from "@/components/Details/AdditionalContent.vue";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import Cover from "@/components/Details/Cover.vue";
import Emulation from "@/components/Details/Emulation.vue";
import Info from "@/components/Details/Info/Base.vue";
import RelatedGames from "@/components/Details/RelatedGames.vue";
import Saves from "@/components/Details/Saves.vue";
import States from "@/components/Details/States.vue";
import TitleInfo from "@/components/Details/Title.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useDisplay, useTheme } from "vuetify";

const route = useRoute();
const rom = ref<Rom>();
const platform = ref<PlatformSchema>();
const tab = ref<
  | "details"
  | "saves"
  | "states"
  | "additionalcontent"
  | "screenshots"
  | "relatedgames"
  | "emulation"
>("details");
const theme = useTheme();
const { smAndDown, mdAndDown, mdAndUp, lgAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const showEmulation = ref(false);
emitter?.on("showEmulation", () => {
  showEmulation.value = !showEmulation.value;
  tab.value = showEmulation.value ? "emulation" : "details";
});

async function fetchDetails() {
  if (!route.params.rom) return;

  await romApi
    .getRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });

  await platformApi
    .getPlatform(rom.value?.platform_id)
    .then((response) => {
      platform.value = response.data;
    })
    .catch((error) => {
      console.log(error);
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

onBeforeMount(async () => {
  emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
  if (rom.value) {
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
  } else {
    await fetchDetails();
  }
  const downloadStore = storeDownload();
  downloadStore.clear();
});

watch(
  () => route.fullPath,
  async () => {
    await fetchDetails();
  }
);
</script>

<template>
  <template v-if="rom && platform">
    <background-header :rom="rom" />

    <v-row
      :class="{
        'mx-12': mdAndUp,
        'justify-center': smAndDown,
      }"
      no-gutters
    >
      <v-col
        class="cover"
        :class="{
          'cover-lg': mdAndUp,
          'cover-xs': smAndDown,
        }"
      >
        <cover
          :romId="rom.id"
          :src="
            !rom.igdb_id && !rom.moby_id && !rom.has_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
              : !rom.has_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : `/assets/romm/resources/${rom.path_cover_l}`
          "
          :lazy-src="
            !rom.igdb_id && !rom.moby_id && !rom.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
              : !rom.has_cover
              ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
              : `/assets/romm/resources/${rom.path_cover_s}`
          "
        />
        <action-bar class="mt-2" :rom="rom" />
        <related-games class="mt-3 px-2" v-if="mdAndUp" :rom="rom" />
      </v-col>
      <v-col
        cols="12"
        sm="12"
        md="7"
        lg="6"
        xl="8"
        class="px-5"
        :class="{
          'info-lg': mdAndUp,
          'info-xs': smAndDown,
        }"
      >
        <v-col
          cols="12"
          sm="12"
          md="6"
          lg="5"
          xl="6"
          class="px-0"
          :class="{
            'position-absolute title-lg': mdAndUp,
            'justify-center': smAndDown,
          }"
        >
          <title-info :rom="rom" :platform="platform" />
        </v-col>
        <v-row
          :class="{
            'justify-center': smAndDown,
          }"
          no-gutters
        >
          <v-tabs
            v-if="!showEmulation"
            v-model="tab"
            slider-color="romm-accent-1"
            rounded="0"
          >
            <v-tab value="details" rounded="0">Details</v-tab>
            <v-tab value="saves" rounded="0">Saves</v-tab>
            <v-tab value="states" rounded="0">States</v-tab>
            <v-tab
              v-if="
                mdAndDown &&
                ((rom.igdb_metadata?.expansions ?? []).length > 0 ||
                  (rom.igdb_metadata?.dlcs ?? []).length > 0)
              "
              value="additionalcontent"
              rounded="0"
              >Additional content</v-tab
            >
            <!-- TODO: user screenshots -->
            <!-- <v-tab value="screenshots" rounded="0">Screenshots</v-tab> -->
            <v-tab
              v-if="
                smAndDown &&
                ((rom.igdb_metadata?.remakes ?? []).length > 0 ||
                  (rom.igdb_metadata?.remasters ?? []).length > 0 ||
                  (rom.igdb_metadata?.expanded_games ?? []).length > 0)
              "
              value="relatedgames"
              rounded="0"
              >Related Games</v-tab
            >
          </v-tabs>
          <v-tabs
            v-if="showEmulation"
            v-model="tab"
            slider-color="romm-accent-1"
            rounded="0"
          >
            <v-tab value="emulation" rounded="0">Emulation</v-tab>
          </v-tabs>
        </v-row>
        <v-row no-gutters class="mb-4">
          <v-col cols="12">
            <v-window v-if="!showEmulation" v-model="tab" class="py-2">
              <v-window-item value="details">
                <info :rom="rom" :platform="platform" />
              </v-window-item>
              <v-window-item value="saves">
                <saves :rom="rom" />
              </v-window-item>
              <v-window-item value="states">
                <states :rom="rom" />
              </v-window-item>
              <v-window-item
                v-if="
                  mdAndDown &&
                  (rom.igdb_metadata?.expansions || rom.igdb_metadata?.dlcs)
                "
                value="additionalcontent"
              >
                <additional-content :rom="rom" />
              </v-window-item>
              <!-- TODO: user screenshots -->
              <!-- <v-window-item v-if="rom.user_screenshots.lenght > 0" value="screenshots">
                <screenshots :rom="rom" />
              </v-window-item> -->
              <v-window-item
                v-if="
                  smAndDown &&
                  (rom.igdb_metadata?.remakes ||
                    rom.igdb_metadata?.remasters ||
                    rom.igdb_metadata?.expanded_games)
                "
                value="relatedgames"
              >
                <related-games :rom="rom" />
              </v-window-item>
            </v-window>
            <v-window v-if="showEmulation" v-model="tab" class="py-2">
              <v-window-item value="emulation">
                <emulation :rom="rom" />
              </v-window-item>
            </v-window>
          </v-col>
        </v-row>
      </v-col>

      <template v-if="lgAndUp">
        <v-col class="px-6">
          <additional-content :rom="rom" />
        </v-col>
      </template>
    </v-row>
  </template>
</template>

<style scoped>
.cover {
  min-width: 270px;
  min-height: 360px;
  max-width: 270px;
  max-height: 360px;
}
.cover-lg {
  margin-top: -230px;
}
.title-lg {
  margin-top: -190px;
}
.cover-xs {
  margin-top: -280px;
}
.info-xs {
  margin-top: 50px;
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}
</style>
