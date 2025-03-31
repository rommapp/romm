<script setup lang="ts">
import HomeBtn from "@/components/common/Navigation/HomeBtn.vue";
import PlatformsBtn from "@/components/common/Navigation/PlatformsBtn.vue";
import CollectionsBtn from "@/components/common/Navigation/CollectionsBtn.vue";
import ScanBtn from "@/components/common/Navigation/ScanBtn.vue";
import SearchBtn from "@/components/common/Navigation/SearchBtn.vue";
import UploadBtn from "@/components/common/Navigation/UploadBtn.vue";
import UserBtn from "@/components/common/Navigation/UserBtn.vue";
import PlatformsDrawer from "@/components/common/Navigation/PlatformsDrawer.vue";
import CollectionsDrawer from "@/components/common/Navigation/CollectionsDrawer.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import SettingsDrawer from "@/components/common/Navigation/SettingsDrawer.vue";
import navigationStore from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { ref } from "vue";

// Props
const { smAndDown } = useDisplay();
const storeNavigation = navigationStore();
const { mainBarCollapsed } = storeToRefs(storeNavigation);

// Functions
function collapse() {
  mainBarCollapsed.value = !mainBarCollapsed.value;
  localStorage.setItem("settings.mainBarCollapsed", mainBarCollapsed.value);
}
</script>
<template>
  <!-- Mobile bottom bar -->
  <v-bottom-navigation
    elevation="0"
    class="bg-background align-center"
    v-if="smAndDown"
  >
    <home-btn value="home" class="mt-2 mr-4" />
    <search-btn value="search" />
    <platforms-btn value="platforms" />
    <collections-btn value="collections" />
    <upload-btn value="upload" />
    <scan-btn value="scan" />
    <user-btn value="user" class="mt-2 ml-4" />
  </v-bottom-navigation>

  <!-- Desktop app bar -->
  <v-navigation-drawer
    v-else
    permanent
    rail
    :rail-width="mainBarCollapsed ? 60 : 100"
    class="bg-background pa-1"
    :border="0"
  >
    <template #prepend>
      <v-row no-gutters class="my-2 justify-center">
        <home-btn />
      </v-row>
    </template>

    <v-row no-gutters class="justify-center mt-10">
      <v-divider class="mx-2" />
      <v-btn
        @click="collapse"
        id="collapseBtn"
        size="small"
        density="comfortable"
        variant="flat"
        rounded
        icon
        ><v-icon>{{
          mainBarCollapsed
            ? "mdi-chevron-double-right"
            : "mdi-chevron-double-left"
        }}</v-icon></v-btn
      >
    </v-row>

    <search-btn :withTag="!mainBarCollapsed" rounded class="mt-3" block />
    <platforms-btn :withTag="!mainBarCollapsed" rounded class="mt-3" block />
    <collections-btn :withTag="!mainBarCollapsed" rounded class="mt-3" block />
    <upload-btn :withTag="!mainBarCollapsed" rounded class="mt-3" block />
    <scan-btn :withTag="!mainBarCollapsed" rounded class="mt-3" block />

    <template #append>
      <v-row no-gutters class="my-2 justify-center">
        <user-btn />
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
