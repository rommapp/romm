<script setup>
import { views } from "@/utils/utils";
import storeGalleryView from "@/stores/galleryView";

// Props
const galleryView = storeGalleryView();
</script>

<template>
  <v-btn
    @click="galleryView.next()"
    rounded="0"
    variant="text"
    class="mr-0"
    :icon="views[galleryView.value]['icon']"
  >
  </v-btn>
</template>
