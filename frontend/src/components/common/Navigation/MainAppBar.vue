<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import CollectionsBtn from "@/components/common/Navigation/CollectionsBtn.vue";
import CollectionsDrawer from "@/components/common/Navigation/CollectionsDrawer.vue";
import ConsoleModeBtn from "@/components/common/Navigation/ConsoleModeBtn.vue";
import HomeBtn from "@/components/common/Navigation/HomeBtn.vue";
import PlatformsBtn from "@/components/common/Navigation/PlatformsBtn.vue";
import PlatformsDrawer from "@/components/common/Navigation/PlatformsDrawer.vue";
import ScanBtn from "@/components/common/Navigation/ScanBtn.vue";
import SearchBtn from "@/components/common/Navigation/SearchBtn.vue";
import SettingsDrawer from "@/components/common/Navigation/SettingsDrawer.vue";
import UploadBtn from "@/components/common/Navigation/UploadBtn.vue";
import UserBtn from "@/components/common/Navigation/UserBtn.vue";
import storeNavigation from "@/stores/navigation";

const { smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { mainBarCollapsed } = storeToRefs(navigationStore);

const mainBarCollapsedStorage = useLocalStorage(
  "settings.mainBarCollapsed",
  false,
);

function collapse() {
  mainBarCollapsed.value = !mainBarCollapsed.value;
  mainBarCollapsedStorage.value = mainBarCollapsed.value;
}
</script>
<template>
  <!-- Mobile top bar -->
  <template v-if="smAndDown">
    <v-app-bar
      elevation="0"
      class="bg-background justify-center px-1"
      height="50"
      fixed
      left
    >
      <template #prepend>
        <home-btn class="ml-1" />
      </template>

      <template #append>
        <upload-btn class="mr-2" />
        <user-btn class="mr-1" />
      </template>
    </v-app-bar>

    <!-- Mobile bottom bar -->
    <v-bottom-navigation
      grow
      elevation="0"
      class="bg-background align-center justify-center"
    >
      <search-btn with-tag />
      <platforms-btn with-tag />
      <collections-btn with-tag />
      <scan-btn with-tag />
      <console-mode-btn with-tag />
    </v-bottom-navigation>
  </template>

  <!-- Desktop app side bar -->
  <v-navigation-drawer
    v-if="!smAndDown"
    permanent
    rail
    :rail-width="mainBarCollapsed ? 60 : 90"
    class="bg-background px-2 py-1"
    :border="0"
  >
    <template #prepend>
      <v-row no-gutters class="my-2 justify-center">
        <home-btn aria-label="Home" tabindex="1" />
      </v-row>
    </template>

    <v-row no-gutters class="justify-center mt-10">
      <v-divider class="mx-2" />
      <v-btn
        id="collapseBtn"
        aria-label="Collapse main navbar"
        tabindex="2"
        size="small"
        density="comfortable"
        variant="flat"
        rounded
        icon
        @click="collapse"
      >
        <v-icon>
          {{
            mainBarCollapsed
              ? "mdi-chevron-double-right"
              : "mdi-chevron-double-left"
          }}
        </v-icon>
      </v-btn>
    </v-row>
    <search-btn
      :with-tag="!mainBarCollapsed"
      rounded
      class="mt-4"
      block
      tabindex="3"
    />
    <platforms-btn
      :with-tag="!mainBarCollapsed"
      rounded
      class="mt-2"
      block
      tabindex="4"
    />
    <collections-btn
      :with-tag="!mainBarCollapsed"
      rounded
      class="mt-2"
      block
      tabindex="5"
    />
    <scan-btn
      :with-tag="!mainBarCollapsed"
      rounded
      class="mt-2"
      block
      tabindex="7"
    />
    <console-mode-btn
      :with-tag="!mainBarCollapsed"
      rounded
      class="mt-2"
      block
      tabindex="8"
    />

    <template #append>
      <upload-btn
        :with-tag="!mainBarCollapsed"
        rounded
        class="mt-2 mb-6"
        block
        tabindex="9"
      />
      <v-row no-gutters class="my-2 justify-center">
        <user-btn tabindex="10" aria-label="Settings menu" />
      </v-row>
    </template>
  </v-navigation-drawer>

  <platforms-drawer />
  <collections-drawer />
  <upload-rom-dialog />
  <settings-drawer />
</template>
<style scoped>
#collapseBtn {
  transform: translateY(-50%);
}
</style>
