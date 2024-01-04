<script setup lang="ts">
import { ref, inject, onBeforeMount, watch } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import api from "@/services/api";
import storeRoms, { type Rom } from "@/stores/roms";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import TitleInfo from "@/components/Details/Title.vue";
import Cover from "@/components/Details/Cover.vue";
import ActionBar from "@/components/Details/ActionBar.vue";
import DetailsInfo from "@/components/Details/Info.vue";
import ScreenshotsCarousel from "@/components/Details/ScreenshotsCarousel.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";
import type { EnhancedRomSchema } from "@/__generated__";

const route = useRoute();
const romsStore = storeRoms();
const rom = ref<EnhancedRomSchema | null>(null);
const tab = ref<"details" | "saves" | "screenshots">("details");
const { smAndDown, mdAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");

async function fetchRom() {
  if (!route.params.rom) return;

  await api
    .fetchRom({ romId: parseInt(route.params.rom as string) })
    .then((response) => {
      rom.value = response.data;
      romsStore.update(response.data);
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
    fetchRom();
  }
});

watch(
  () => route.fullPath,
  async () => {
    emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
    await fetchRom();
  }
);
</script>

<template>
  <template v-if="rom">
    <v-row no-gutters>
      <v-col>
        <background-header :image="rom.path_cover_s" />
      </v-col>
    </v-row>

    <v-row
      :class="{
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
        cols="12"
        md="6"
        lg="6"
      >
        <cover :rom="rom" />
        <action-bar class="mt-2" :rom="rom" />
      </v-col>
      <v-col
        cols="12"
        md="6"
        lg="6"
        class="px-6"
        :class="{
          'mr-16 info-lg': mdAndUp,
          'info-xs': smAndDown,
        }"
      >
        <v-row :class="{ 'position-absolute title-lg': mdAndUp }" no-gutters>
          <title-info :rom="rom" />
        </v-row>
        <v-row no-gutters>
          <v-tabs v-model="tab" slider-color="romm-accent-1" rounded="0">
            <v-tab value="details" rounded="0">Details</v-tab>
            <v-tab value="saves" rounded="0" disabled
              >Saves<span class="text-caption text-truncate ml-1"
                >[coming soon]</span
              ></v-tab
            >
            <v-tab
              v-if="rom.path_screenshots.length > 0"
              value="screenshots"
              rounded="0"
              >Screenshots</v-tab
            >
          </v-tabs>
        </v-row>
        <v-row no-gutters>
          <v-col cols="12">
            <v-window v-model="tab" class="mt-2">
              <v-window-item value="details">
                <details-info :rom="rom" />
              </v-window-item>
              <v-window-item value="screenshots">
                <screenshots-carousel :rom="rom" />
              </v-window-item>
              <v-window-item value="saves">
                <v-row class="d-flex mt-2"></v-row>
              </v-window-item>
            </v-window>
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </template>

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
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
  margin-left: 110px;
}
.cover-xs {
  margin-top: -280px;
}
.title-lg {
  margin-top: -190px;
}
.info-xs {
  margin-top: 60px;
}
</style>
