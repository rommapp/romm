<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import CollectionInfoDrawer from "@/components/Gallery/AppBar/Collection/CollectionInfoDrawer.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import { storeToRefs } from "pinia";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const navigationStore = storeNavigation();
const { activeCollectionInfoDrawer } = storeToRefs(navigationStore);
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);
</script>

<template>
  <v-app-bar
    id="gallery-app-bar"
    elevation="0"
    density="compact"
    mode="shift"
    app
    fixed
    top
  >
    <template #prepend>
      <!-- <v-btn
        :color="activeCollectionInfoDrawer ? 'romm-accent-1' : ''"
        rounded="0"
        @click="navigationStore.swtichActiveCollectionInfoDrawer"
        icon="mdi-information"
      ></v-btn> -->
      <r-avatar
        @click="navigationStore.swtichActiveCollectionInfoDrawer"
        class="collection-icon cursor-pointer"
        v-if="currentCollection"
        :size="75"
        :collection="currentCollection"
      />
      <filter-btn />
    </template>
    <filter-text-field v-if="!xs" />
    <template #append>
      <selecting-btn />
      <gallery-view-btn />
    </template>
  </v-app-bar>

  <collection-info-drawer />
  <filter-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
.collection-icon {
  transition:
    filter 0.15s ease-in-out,
    transform 0.15s ease-in-out;
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
.collection-icon:hover,
.collection-icon.active {
  filter: drop-shadow(0px 0px 3px rgba(var(--v-theme-romm-accent-1)));
  transform: scale(1.1);
}
</style>
