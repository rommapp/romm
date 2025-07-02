<script setup lang="ts">
import BaseGalleryAppBar from "@/components/Gallery/AppBar/Base.vue";
import CollectionInfoDrawer from "@/components/Gallery/AppBar/Collection/CollectionInfoDrawer.vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const navigationStore = storeNavigation();
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);
</script>

<template>
  <base-gallery-app-bar show-platforms-filter :show-search-bar="!xs">
    <template #prepend>
      <r-avatar
        v-if="currentCollection"
        @click="navigationStore.switchActiveCollectionInfoDrawer"
        class="collection-icon cursor-pointer"
        :size="45"
        :collection="currentCollection"
      />
    </template>
  </base-gallery-app-bar>

  <collection-info-drawer />
</template>

<style scoped>
.collection-icon {
  transition:
    filter 0.15s ease-in-out,
    transform 0.15s ease-in-out;
}
.collection-icon:hover,
.collection-icon.active {
  transform: scale(1.1);
}
</style>
