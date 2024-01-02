<script setup lang="ts">
import { views } from "@/utils";
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
    :icon="views[galleryView.current]['icon']"
  >
  </v-btn>
</template>
@/utils
