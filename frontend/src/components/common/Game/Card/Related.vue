<script setup lang="ts">
import type { IGDBRelatedGame } from "@/__generated__";
import storeGalleryView from "@/stores/galleryView";
import { getMissingCoverImage } from "@/utils/covers";
import { computed } from "vue";

// Props
const props = defineProps<{
  game: IGDBRelatedGame;
}>();
const galleryViewStore = storeGalleryView();

const missingCoverImage = computed(() => getMissingCoverImage(props.game.name));
</script>

<template>
  <a :href="`https://www.igdb.com/games/${game.slug}`" target="_blank">
    <v-card>
      <v-tooltip
        activator="parent"
        location="top"
        class="tooltip"
        transition="fade-transition"
        open-delay="1000"
        >{{ game.name }}</v-tooltip
      >
      <v-img
        v-bind="props"
        :src="game.cover_url || missingCoverImage"
        :aspect-ratio="galleryViewStore.defaultAspectRatioCover"
        cover
        lazy
      >
        <v-chip
          class="px-2 position-absolute chip-type text-white translucent-dark"
          density="compact"
          label
        >
          <span>
            {{ game.type }}
          </span>
        </v-chip>
        <template #error>
          <v-img :src="missingCoverImage" />
        </template>
      </v-img>
    </v-card>
  </a>
</template>
<style scoped>
.chip-type {
  top: -0.1rem;
  left: -0.1rem;
}
</style>
