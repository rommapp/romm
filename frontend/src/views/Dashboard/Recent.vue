<script setup>
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { views } from "@/utils/utils";
import { fetchRecentRoms } from "@/services/api";
import storeRoms from "@/stores/roms";
import GameCard from "@/components/Game/Card/Base.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import UploadRomDialog from "@/components/Dialog/Rom/UploadRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";

// Props
const romsStore = storeRoms();
const { selectedRoms, searchRoms, cursor, searchCursor } =
  storeToRefs(romsStore);
onMounted(async () => {
  const { data: recentData } = await fetchRecentRoms();
  romsStore.setRecentRoms(recentData);
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
    <v-card-text>
      <v-row>
        <v-col
          class="pa-1"
          v-for="rom in romsStore.recentRoms"
          :key="rom.id"
          :cols="views[0]['size-cols']"
          :xs="views[0]['size-xs']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
        >
          <game-card :rom="rom" :showSelector="false" />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <search-rom-dialog />
  <upload-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>
