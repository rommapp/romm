<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RSection from "@/components/common/RSection.vue";
import storeRoms from "@/stores/roms";
import { views } from "@/utils";
import { storeToRefs } from "pinia";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";
import { ref } from "vue";

// Props
const { t } = useI18n();
const romsStore = storeRoms();
const { recentRoms } = storeToRefs(romsStore);
const storedGridRecentRoms = localStorage.getItem("settings.gridRecentRoms");
const gridRecentRoms = ref(
  isNull(storedGridRecentRoms) ? false : storedGridRecentRoms === "true",
);
function toggleGridRecentRoms() {
  gridRecentRoms.value = !gridRecentRoms.value;
  localStorage.setItem(
    "settings.gridRecentRoms",
    gridRecentRoms.value.toString(),
  );
}
</script>
<template>
  <r-section icon="mdi-shimmer" :title="t('home.recently-added')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle recently games added grid view"
        icon
        rounded="0"
        @click="toggleGridRecentRoms"
        ><v-icon>{{
          gridRecentRoms ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridRecentRoms,
        }"
        class="pa-1"
        no-gutters
      >
        <v-col
          v-for="rom in recentRoms"
          :key="rom.id"
          class="pa-1 align-self-end"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <game-card
            :key="rom.updated_at"
            :rom="rom"
            titleOnHover
            pointerOnHover
            withLink
            showFlags
            showFav
            transformScale
            showActionBar
            showPlatformIcon
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
