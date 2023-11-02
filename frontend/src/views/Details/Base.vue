<script setup>
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";
import { fetchRomApi } from "@/services/api";
import storeRoms from "@/stores/roms";
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

// Props
const route = useRoute();
const romsStore = storeRoms();
const { allRoms } = storeToRefs(romsStore);
const rom = ref(allRoms.value.find((rom) => rom.id == route.params.rom));
const tab = ref("details");
const downloadUrl = ref();
const { xs, mdAndDown, lgAndUp } = useDisplay();

// Event listeners bus
const emitter = inject("emitter");

// Functions
onBeforeMount(async () => {
  emitter.emit("showLoadingDialog", { loading: true, scrim: false });
  if (rom.value) {
    emitter.emit("showLoadingDialog", { loading: false, scrim: false });
  } else {
    await fetchRomApi(route.params.platform, route.params.rom)
      .then((response) => {
        rom.value = response.data;
        romsStore.update(response.data);
        downloadUrl.value = `${window.location.origin}${rom.value.download_path}`;
      })
      .catch((error) => {
        console.log(error);
        emitter.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
      })
      .finally(() => {
        emitter.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }
});
</script>

<template>
  <background-header v-if="rom" :image="rom.path_cover_s" />

  <v-row
    v-if="rom"
    class="justify-center"
    :class="{
      content: lgAndUp,
      'content-tablet': mdAndDown,
      'content-mobile': xs,
    }"
    no-gutters
  >
    <v-col
      :class="{
        cover: lgAndUp,
        'cover-tablet': mdAndDown,
        'cover-mobile': xs,
      }"
      class="pa-3 mr-2"
    >
      <cover :rom="rom" />
      <action-bar :rom="rom" :downloadUrl="downloadUrl" />
    </v-col>
    <v-col
      class="mt-14"
      :class="{ info: lgAndUp, 'info-tablet': mdAndDown, 'info-mobile': xs }"
    >
      <title-info :rom="rom" />
      <div
        :class="{
          'details-content': lgAndUp,
          'details-content-tablet': mdAndDown,
          'details-content-mobile': xs,
        }"
      >
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
        <v-window v-model="tab" class="mt-2">
          <v-window-item value="details">
            <details-info :rom="rom" />
          </v-window-item>
          <v-window-item value="screenshots">
            <screenshots-carousel :rom="rom" />
          </v-window-item>
          <v-window-item value="saves">
            <v-row class="d-flex mt-2" no-gutters></v-row>
          </v-window-item>
        </v-window>
      </div>
    </v-col>
  </v-row>

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>

<style scoped>
.scroll {
  overflow-y: scroll;
}

.content,
.content-tablet,
.content-mobile {
  /* Needed to put elements on top of the header background */
  position: relative;
}

.content,
.content-tablet {
  margin-top: 88px;
  margin-left: 100px;
  margin-right: 100px;
}

.content-mobile {
  margin-top: 64px;
  margin-left: 20px;
  margin-right: 20px;
}

.cover,
.cover-tablet {
  min-width: 295px;
  min-height: 396px;
  max-width: 295px;
  max-height: 396px;
}
.cover-mobile {
  min-width: 265px;
  min-height: 346px;
  max-width: 265px;
  max-height: 346px;
}

.details,
.details-tablet,
.details-mobile {
  padding-left: 25px;
  padding-right: 25px;
}

.details-content {
  margin-top: 98px;
  max-width: 700px;
}

.details-content-tablet {
  margin-top: 66px;
}

.details-content-mobile {
  margin-top: 30px;
}
</style>
