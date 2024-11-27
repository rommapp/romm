<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RSection from "@/components/common/RSection.vue";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import { views } from "@/utils";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

// Props
const romsStore = storeRoms();
const { recentRoms } = storeToRefs(romsStore);
const router = useRouter();

// Functions
function onGameClick(emitData: { rom: SimpleRom; event: MouseEvent }) {
  if (emitData.event.metaKey || emitData.event.ctrlKey) {
    const link = router.resolve({
      name: "rom",
      params: { rom: emitData.rom.id },
    });
    window.open(link.href, "_blank");
  } else {
    router.push({ name: "rom", params: { rom: emitData.rom.id } });
  }
}
</script>
<template>
  <r-section icon="mdi-shimmer" title="Recently added">
    <template #content>
      <v-row class="flex-nowrap overflow-x-auto" no-gutters>
        <v-col
          v-for="rom in recentRoms"
          :key="rom.id"
          class="px-1 pt-1 pb-2"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <game-card
            :key="rom.updated_at"
            @click="onGameClick"
            :rom="rom"
            title-on-hover
            show-flags
            show-fav
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
