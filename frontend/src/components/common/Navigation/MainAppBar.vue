<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import RandomBtn from "@/components/Gallery/AppBar/common/RandomBtn.vue";
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
        <HomeBtn class="ml-1" />
      </template>

      <template #append>
        <RandomBtn />
        <UploadBtn class="mr-2" />
        <UserBtn class="mr-1" />
      </template>
    </v-app-bar>

    <!-- Mobile bottom bar -->
    <v-bottom-navigation
      grow
      elevation="0"
      class="bg-background align-center justify-center"
    >
      <SearchBtn with-tag />
      <PlatformsBtn with-tag />
      <CollectionsBtn with-tag />
      <ScanBtn with-tag />
      <ConsoleModeBtn with-tag />
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
        <HomeBtn aria-label="Home" />
      </v-row>
    </template>

    <v-row no-gutters class="justify-center mt-10">
      <v-divider class="mx-2" />
      <v-btn
        id="collapseBtn"
        aria-label="Collapse main navbar"
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
    <SearchBtn :with-tag="!mainBarCollapsed" rounded class="mt-4" block />
    <PlatformsBtn :with-tag="!mainBarCollapsed" rounded class="mt-2" block />
    <CollectionsBtn :with-tag="!mainBarCollapsed" rounded class="mt-2" block />
    <ScanBtn :with-tag="!mainBarCollapsed" rounded class="mt-2" block />
    <ConsoleModeBtn :with-tag="!mainBarCollapsed" rounded class="mt-2" block />

    <template #append>
      <RandomBtn :with-tag="!mainBarCollapsed" rounded class="mt-2" block />
      <UploadBtn
        :with-tag="!mainBarCollapsed"
        rounded
        class="mt-2 mb-6"
        block
      />
      <v-row no-gutters class="my-2 justify-center">
        <UserBtn aria-label="Settings menu" />
      </v-row>
    </template>
  </v-navigation-drawer>

  <PlatformsDrawer />
  <CollectionsDrawer />
  <UploadRomDialog />
  <SettingsDrawer />
</template>
<style scoped>
#collapseBtn {
  transform: translateY(-50%);
}
</style>
