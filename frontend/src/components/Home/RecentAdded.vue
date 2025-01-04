<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RSection from "@/components/common/RSection.vue";
import storeRoms from "@/stores/roms";
import { views } from "@/utils";
import { storeToRefs } from "pinia";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const romsStore = storeRoms();
const { recentRoms } = storeToRefs(romsStore);
const gridRecentRoms = isNull(localStorage.getItem("settings.gridRecentRoms"))
  ? false
  : localStorage.getItem("settings.gridRecentRoms") === "true";
</script>
<template>
  <r-section icon="mdi-shimmer" :title="t('home.recently-added')">
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridRecentRoms }"
        no-gutters
      >
        <v-col
          v-for="rom in recentRoms"
          :key="rom.id"
          class="px-1 pt-1 pb-2 align-self-end"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <game-card
            :key="rom.updated_at"
            :rom="rom"
            title-on-hover
            pointer-on-hover
            with-link
            show-flags
            show-fav
            transform-scale
            show-action-bar
            show-platform-icon
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
