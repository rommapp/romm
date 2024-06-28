<script setup lang="ts">
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";

// Props
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const { activePlatformsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="400"
    v-model="activePlatformsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <platform-list-item
        v-for="platform in platformsStore.filledPlatforms"
        :key="platform.slug"
        :platform="platform"
        class="py-4"
      />
    </v-list>
  </v-navigation-drawer>
</template>
