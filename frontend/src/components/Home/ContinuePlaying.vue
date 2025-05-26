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
const { continuePlayingRoms } = storeToRefs(romsStore);
const storedContinuePlaying = localStorage.getItem(
  "settings.gridContinuePlayingRoms",
);
const gridContinuePlayingRoms = ref(
  isNull(storedContinuePlaying) ? false : storedContinuePlaying === "true",
);
const storedEnable3DEffect = localStorage.getItem("settings.enable3DEffect");
const enable3DEffect = ref(
  isNull(storedEnable3DEffect) ? false : storedEnable3DEffect === "true",
);
const isHovering = ref(false);
const hoveringRomId = ref();
const openedMenu = ref(false);
const openedMenuRomId = ref();

// Functions
function toggleGridContinuePlaying() {
  gridContinuePlayingRoms.value = !gridContinuePlayingRoms.value;
  localStorage.setItem(
    "settings.gridContinuePlayingRoms",
    gridContinuePlayingRoms.value.toString(),
  );
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
  openedMenuRomId.value = null;
}
</script>
<template>
  <r-section icon="mdi-play" :title="t('home.continue-playing')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle continue playing games grid view"
        icon
        rounded="0"
        @click="toggleGridContinuePlaying"
        ><v-icon>{{
          gridContinuePlayingRoms ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridContinuePlayingRoms,
        }"
        class="pa-1"
        no-gutters
        style="overflow-y: hidden"
      >
        <v-col
          v-for="rom in continuePlayingRoms"
          :key="rom.id"
          class="pa-1 align-self-end my-4"
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
            :enable3DTilt="enable3DEffect"
            @hover="onHover"
            @openedmenu="onOpenedMenu"
            @closedmenu="onClosedMenu"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
