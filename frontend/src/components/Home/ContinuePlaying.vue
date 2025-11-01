<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import GameCard from "@/components/common/Game/Card/Base.vue";
import RSection from "@/components/common/RSection.vue";
import storeRoms from "@/stores/roms";
import { views } from "@/utils";

const { t } = useI18n();
const romsStore = storeRoms();
const { continuePlayingRoms } = storeToRefs(romsStore);
const gridContinuePlayingRoms = useLocalStorage(
  "settings.gridContinuePlayingRoms",
  false,
);
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
const isHovering = ref(false);
const hoveringRomId = ref<number>();
const openedMenu = ref(false);
const openedMenuRomId = ref<number>();

function toggleGridContinuePlaying() {
  gridContinuePlayingRoms.value = !gridContinuePlayingRoms.value;
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringRomId.value = emitData.id;
}

function onOpenedMenu(emitData: { openedMenu: boolean; id: number }) {
  openedMenu.value = emitData.openedMenu;
  openedMenuRomId.value = emitData.id;
}

function onClosedMenu() {
  openedMenu.value = false;
  openedMenuRomId.value = undefined;
}
</script>
<template>
  <RSection icon="mdi-play" :title="t('home.continue-playing')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle continue playing games grid view"
        icon
        rounded="0"
        @click="toggleGridContinuePlaying"
      >
        <v-icon>
          {{ gridContinuePlayingRoms ? "mdi-view-comfy" : "mdi-view-column" }}
        </v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridContinuePlayingRoms }"
        class="py-1 overflow-y-hidden"
        no-gutters
      >
        <v-col
          v-for="rom in continuePlayingRoms"
          :key="rom.id"
          class="pa-1 align-self-end"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <GameCard
            :key="rom.updated_at"
            :rom="rom"
            title-on-hover
            pointer-on-hover
            with-link
            transform-scale
            show-action-bar
            show-chips
            :enable3-d-tilt="enable3DEffect"
            force-boxart="cover_path"
            @hover="onHover"
            @focus="onHover"
            @openedmenu="onOpenedMenu"
            @closedmenu="onClosedMenu"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
