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
const { recentRoms } = storeToRefs(romsStore);
const gridRecentRoms = useLocalStorage("settings.gridRecentRoms", false);
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
const isHovering = ref(false);
const hoveringRomId = ref<number>();
const openedMenu = ref(false);
const openedMenuRomId = ref<number>();

function toggleGridRecentRoms() {
  gridRecentRoms.value = !gridRecentRoms.value;
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
  <RSection icon="mdi-shimmer" :title="t('home.recently-added')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle recently games added grid view"
        icon
        rounded="0"
        @click="toggleGridRecentRoms"
      >
        <v-icon>
          {{ gridRecentRoms ? "mdi-view-comfy" : "mdi-view-column" }}
        </v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridRecentRoms }"
        class="py-1 overflow-y-hidden"
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
          :style="{
            zIndex:
              (isHovering && hoveringRomId === rom.id) ||
              (openedMenu && openedMenuRomId === rom.id)
                ? 1000
                : 1,
          }"
        >
          <GameCard
            :key="rom.updated_at"
            :rom="rom"
            title-on-hover
            pointer-on-hover
            with-link
            transform-scale
            show-chips
            show-action-bar
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
