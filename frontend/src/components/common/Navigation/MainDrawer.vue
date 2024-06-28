<script setup lang="ts">
import HomeBtn from "@/components/common/Navigation/HomeBtn.vue";
import PlatformsBtn from "@/components/common/Navigation/PlatformsBtn.vue";
import ScanBtn from "@/components/common/Navigation/ScanBtn.vue";
import SearchBtn from "@/components/common/Navigation/SearchBtn.vue";
import UploadBtn from "@/components/common/Navigation/UploadBtn.vue";
import UserBtn from "@/components/common/Navigation/UserBtn.vue";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";

// Props
const navigationStore = storeNavigation();
const { activePlatformsDrawer, activeSettingsDrawer } =
  storeToRefs(navigationStore);
</script>
<template>
  <v-navigation-drawer
    permanent
    rail
    :floating="activePlatformsDrawer || activeSettingsDrawer"
    rail-width="60"
  >
    <template #prepend>
      <v-row no-gutters class="my-2 justify-center">
        <home-btn />
      </v-row>
      <v-row no-gutters class="my-4 justify-center">
        <search-btn />
        <upload-btn />
      </v-row>
    </template>

    <v-row no-gutters class="justify-center">
      <platforms-btn />
      <scan-btn />
    </v-row>
    <template #append>
      <v-row no-gutters class="my-2 justify-center">
        <user-btn />
      </v-row>
    </template>
  </v-navigation-drawer>
</template>
