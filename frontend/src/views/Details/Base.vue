<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";

import type { EnhancedRomSchema, PlatformSchema } from "@/__generated__";
import ActionBar from "@/components/Details/ActionBar.vue";
import BackgroundHeader from "@/components/Details/BackgroundHeader.vue";
import Cover from "@/components/Details/Cover.vue";
import DeleteAssetDialog from "@/components/Details/DeleteAssets.vue";
import DetailsInfo from "@/components/Details/DetailsInfo.vue";
import Saves from "@/components/Details/Saves.vue";
import Screenshots from "@/components/Details/Screenshots.vue";
import States from "@/components/Details/States.vue";
import TitleInfo from "@/components/Details/Title.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import api from "@/services/api";

const route = useRoute();
const rom = ref<EnhancedRomSchema>();
const platform = ref<PlatformSchema>();
const tab = ref<"details" | "saves" | "screenshots">("details");
const { smAndDown, mdAndUp } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");

async function fetchDetails() {
  if (!route.params.rom) return;

  await api
    .fetchRom({ romId: parseInt(route.params.rom as string) })
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

  await api
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
});

watch(
  () => route.fullPath,
  async () => {
    emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
    await fetchDetails();
  }
);
</script>

<template>
  <template v-if="rom && platform">
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
        <v-row
          :class="{
            'position-absolute title-lg mr-16': mdAndUp,
            'justify-center': smAndDown,
          }"
          no-gutters
        >
          <v-col cols="12">
            
            <title-info :rom="rom" :platform="platform" />
          </v-col>
        </v-row>
        <v-row
          :class="{
            'justify-center': smAndDown,
          }"
          no-gutters
        >
          <v-tabs v-model="tab" slider-color="romm-accent-1" rounded="0">
            <v-tab value="details" rounded="0">Details</v-tab>
            <v-tab value="saves" rounded="0"> Saves </v-tab>
            <v-tab value="states" rounded="0"> States </v-tab>
            <v-tab value="screenshots" rounded="0"> Screenshots </v-tab>
          </v-tabs>
        </v-row>
        <v-row no-gutters class="mb-4">
          <v-col cols="12">
            <v-window v-model="tab" class="py-2">
              <v-window-item value="details">
                <details-info :rom="rom" />
              </v-window-item>
              <v-window-item value="saves">
                <saves :rom="rom" />
              </v-window-item>
              <v-window-item value="states">
                <states :rom="rom" />
              </v-window-item>
              <v-window-item value="screenshots">
                <screenshots :rom="rom" />
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
  <delete-asset-dialog />
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
