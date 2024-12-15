<script setup lang="ts">
import HomeBtn from "@/components/common/Navigation/HomeBtn.vue";
import PlatformsBtn from "@/components/common/Navigation/PlatformsBtn.vue";
import CollectionsBtn from "@/components/common/Navigation/CollectionsBtn.vue";
import ScanBtn from "@/components/common/Navigation/ScanBtn.vue";
import SearchBtn from "@/components/common/Navigation/SearchBtn.vue";
import UploadBtn from "@/components/common/Navigation/UploadBtn.vue";
import UserBtn from "@/components/common/Navigation/UserBtn.vue";
import SearchRomDialog from "@/components/common/Game/Dialog/SearchRom.vue";
import PlatformsDrawer from "@/components/common/Navigation/PlatformsDrawer.vue";
import CollectionsDrawer from "@/components/common/Navigation/CollectionsDrawer.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import SettingsDrawer from "@/components/common/Navigation/SettingsDrawer.vue";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { activePlatformsDrawer, activeCollectionsDrawer, activeSettingsDrawer } =
  storeToRefs(navigationStore);
</script>
<template>
  <!-- Mobile app bar -->
  <v-app-bar
    v-if="smAndDown"
    elevation="0"
    class="bg-primary justify-center px-1"
    mode="shift"
    height="45"
    app
    fixed
    left
  >
    <template #prepend>
      <home-btn />
    </template>

    <search-btn />
    <platforms-btn />
    <collections-btn />
    <v-divider opacity="0" class="mx-3" vertical />
    <upload-btn />
    <scan-btn />

    <template #append>
      <user-btn />
    </template>
  </v-app-bar>

  <!-- Desktop app bar -->
  <v-navigation-drawer
    v-else
    permanent
    rail
    :floating="
      activePlatformsDrawer || activeCollectionsDrawer || activeSettingsDrawer
    "
    rail-width="60"
  >
    <template #prepend>
      <v-row no-gutters class="my-2 justify-center">
        <home-btn />
      </v-row>
    </template>

    <v-divider opacity="0" class="my-4" />
    <search-btn block />
    <platforms-btn block />
    <collections-btn block />
    <v-divider opacity="0" class="my-3" />
    <upload-btn block />
    <scan-btn block />
    <template #append>
      <v-row no-gutters class="my-2 justify-center">
        <user-btn />
      </v-row>
    </template>
  </v-navigation-drawer>

  <search-rom-dialog />
  <platforms-drawer />
  <collections-drawer />
  <upload-rom-dialog />
  <settings-drawer />
</template>
