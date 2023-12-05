<script setup>
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";
import api from "@/services/api";
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
const { xs, sm, md, lgAndUp, name } = useDisplay();

// Event listeners bus
const emitter = inject("emitter");

// Functions
onBeforeMount(async () => {
  emitter.emit("showLoadingDialog", { loading: true, scrim: false });
  if (rom.value) {
    emitter.emit("showLoadingDialog", { loading: false, scrim: false });
  } else {
    await api.fetchRom({ romId: route.params.rom })
      .then((response) => {
        rom.value = response.data;
        romsStore.update(response.data);
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
      'content-tablet-md': md,
      'content-tablet-sm': sm,
      'content-mobile': xs,
    }"
    no-gutters
  >
    <v-col
      :class="{
        cover: lgAndUp,
        'cover-tablet-md': md,
        'cover-tablet-sm': sm,
        'cover-mobile': xs,
      }"
      class="pa-3"
    >
      <cover :rom="rom" />
      <action-bar :rom="rom" />
    </v-col>
    <v-col
      class="mt-14"
      :class="{
        info: lgAndUp,
        'info-tablet-md': md,
        'info-tablet-sm': sm,
        'info-mobile': xs,
      }"
    >
      <title-info :rom="rom" />
      <v-row
        :class="{
          'details-content': lgAndUp,
          'details-content-tablet-md': md,
          'details-content-tablet-sm': sm,
          'details-content-mobile': xs,
        }"
        no-gutters
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
              <v-row class="d-flex mt-2" no-gutters></v-row>
            </v-window-item>
          </v-window>
        </v-col>
      </v-row>
    </v-col>
  </v-row>

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>

<style scoped>
.content,
.content-tablet-md,
.content-tablet-sm,
.content-mobile {
  /* Needed to put elements on top of the header background */
  position: relative;
}

.content,
.content-tablet-md {
  margin-top: 90px;
  margin-left: 100px;
}

.content {
  margin-right: 250px;
}
.content-tablet-md {
  margin-right: 100px;
}

.content-tablet-sm {
  margin-top: 20px;
  margin-left: 50px;
  margin-right: 50px;
}
.content-mobile {
  margin-top: 20px;
  margin-left: 20px;
  margin-right: 20px;
}

.cover,
.cover-tablet-md {
  min-width: 295px;
  min-height: 420px;
  max-width: 295px;
  max-height: 420px;
}
.cover-tablet-sm,
.cover-mobile {
  min-width: 295px;
  min-height: 390px;
  max-width: 295px;
  max-height: 390px;
}

.info,
.info-tablet-md {
  margin-left: 15px;
  min-width: 480px;
}

.details,
.details-tablet-md,
.details-tablet-sm,
.details-mobile {
  position: relative;
  padding-left: 25px;
  padding-right: 25px;
}

.details-content {
  margin-top: 108px;
  max-width: 700px;
}

.details-content-tablet-md {
  margin-top: 52px;
  max-width: 700px;
}

.details-content-tablet-sm,
.details-content-mobile {
  margin-top: 18px;
}
</style>
