<script setup lang="ts">
import LoadingDialog from "@/components/Dialog/Loading.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import UploadRomDialog from "@/components/Dialog/Rom/UploadRom.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import { views } from "@/utils";
import { onMounted, ref } from "vue";

// Props
const romsStore = storeRoms();
const scroll_container = ref();

// Methods
function scrollX(e: WheelEvent) {
  // TODO: fix horizontal scroll with wheel
  scroll_container.value.scrollLeft += e.deltaY;
}

onMounted(() => {
  romApi
    .getRecentRoms()
    .then(({ data: recentData }) => {
      romsStore.setRecentRoms(recentData.items);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact"
      ><v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-shimmer</v-icon>Recently
        added</v-toolbar-title
      ></v-toolbar
    >
    <v-divider class="border-opacity-25" />
    <v-card-text class="scroll">
      <v-row
        ref="scroll_container"
        @mousewheel="scrollX"
        class="flex-nowrap overflow-x-auto"
      >
        <v-col
          class="pa-1 pb-2"
          v-for="rom in romsStore.recentRoms"
          :key="rom.id"
          :cols="views[0]['size-cols']"
          :xs="views[0]['size-xs']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <game-card
            :index="rom.id"
            :rom="rom"
            :selected="false"
            :showSelector="false"
          />
        </v-col>
      </v-row>
      <!-- TODO: Check recently added games in the last 30 days -->
      <!-- TODO: Add a button to upload roms if no roms were uploaded in the last 30 days -->
    </v-card-text>
  </v-card>

  <search-rom-dialog />
  <upload-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>
<style scoped>
.scroll {
  overflow-x: visible;
}
</style>
