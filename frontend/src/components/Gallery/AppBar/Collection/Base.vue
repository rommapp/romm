<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useDisplay } from "vuetify";
import BaseGalleryAppBar from "@/components/Gallery/AppBar/Base.vue";
import CollectionInfoDrawer from "@/components/Gallery/AppBar/Collection/CollectionInfoDrawer.vue";
import SmartCollectionInfoDrawer from "@/components/Gallery/AppBar/Collection/SmartCollectionInfoDrawer.vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";

const { xs } = useDisplay();
const navigationStore = storeNavigation();
const romsStore = storeRoms();
const { currentCollection, currentVirtualCollection, currentSmartCollection } =
  storeToRefs(romsStore);

// Get the currently active collection (any type)
const activeCollection = computed(() => {
  return (
    currentCollection.value ||
    currentVirtualCollection.value ||
    currentSmartCollection.value
  );
});
</script>

<template>
  <BaseGalleryAppBar show-platforms-filter :show-search-bar="!xs">
    <template #prepend>
      <RAvatar
        v-if="activeCollection"
        class="collection-icon cursor-pointer"
        :size="45"
        :collection="activeCollection"
        @click="navigationStore.switchActiveCollectionInfoDrawer"
      />
    </template>
  </BaseGalleryAppBar>

  <CollectionInfoDrawer />
  <SmartCollectionInfoDrawer />
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
