<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import CollectionInfoDrawer from "@/components/Gallery/AppBar/Collection/CollectionInfoDrawer.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import { storeToRefs } from "pinia";
import storeNavigation from "@/stores/navigation";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const navigationStore = storeNavigation();
const { activeCollectionInfoDrawer } = storeToRefs(navigationStore);
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
      <v-btn
        :color="activeCollectionInfoDrawer ? 'romm-accent-1' : ''"
        rounded="0"
        @click="navigationStore.swtichActiveCollectionInfoDrawer"
        icon="mdi-information"
      ></v-btn>
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
</style>
