<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { IGDBRelatedGame } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import { getMissingCoverImage } from "@/utils/covers";

const props = defineProps<{
  game: IGDBRelatedGame;
}>();

const galleryViewStore = storeGalleryView();
const romId = ref<number | null>(null);

const missingCoverImage = computed(() => getMissingCoverImage(props.game.name));
const computedAspectRatio = computed(() =>
  galleryViewStore.getAspectRatio({ boxartStyle: "cover_path" }),
);

const gameLink = computed(() => {
  if (romId.value !== null) {
    return `/rom/${romId.value}`;
  }
  return `https://www.igdb.com/games/${props.game.slug}`;
});

const linkTarget = computed(() => {
  return romId.value !== null ? "_self" : "_blank";
});

onMounted(async () => {
  await romApi
    .getRomByMetadataProvider({ provider: "igdb", id: props.game.id })
    .then((response) => {
      console.log("Fetched ROM by metadata provider:", response.data);
      romId.value = response.data.id;
    })
    .catch((error) => {
      console.error("Error fetching ROM by metadata provider:", error);
      // Keep romId.value as null to fall back to IGDB link
    });
});
</script>

<template>
  <a :href="gameLink" :target="linkTarget">
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
        :aspect-ratio="computedAspectRatio"
        cover
      >
        <v-chip
          class="px-2 position-absolute chip-type text-white translucent"
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
