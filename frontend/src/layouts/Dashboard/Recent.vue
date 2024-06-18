<script setup lang="ts">
import GameCard from "@/components/Game/Card/Base.vue";
import RSection from "@/components/common/Section.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import { views } from "@/utils";
import { onMounted } from "vue";
import { useRouter } from "vue-router";

// Props
const romsStore = storeRoms();
const router = useRouter();

// Functions
function onGameClick(emitData: { rom: SimpleRom; event: MouseEvent }) {
  router.push({ name: "rom", params: { rom: emitData.rom.id } });
}

onMounted(() => {
  romApi
    .getRecentRoms()
    .then(({ data: recentData }) => {
      romsStore.setRecentRoms(recentData);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>
<template>
  <r-section icon="mdi-shimmer" title="Recently added">
    <template #content>
      <v-row class="flex-nowrap overflow-x-auto" no-gutters>
        <v-col
          v-for="rom in romsStore.recentRoms"
          :key="rom.id"
          class="px-1 pt-1 pb-2"
          :cols="views[0]['size-cols']"
          :xs="views[0]['size-xs']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <game-card
            @click="onGameClick"
            :rom="rom"
            transform-scale
            show-action-bar
          />
        </v-col>
      </v-row>
      <!-- TODO: Check recently added games in the last 30 days -->
      <!-- TODO: Add a button to upload roms if no roms were uploaded in the last 30 days -->
    </template>
  </r-section>

</template>
