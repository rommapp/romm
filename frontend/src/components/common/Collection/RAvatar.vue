<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import { getCollectionCoverImage, getFavoriteCoverImage } from "@/utils/covers";
import { computed } from "vue";

const props = withDefaults(
  defineProps<{ collection: Collection; size?: number }>(),
  {
    size: 45,
  },
);

const collectionCoverImage = computed(() =>
  getCollectionCoverImage(props.collection.name),
);
const favoriteCoverImage = computed(() =>
  getFavoriteCoverImage(props.collection.name),
);
</script>

<template>
  <v-avatar :size="size" rounded="0">
    <v-img
      :src="
        collection.has_cover
          ? `/assets/romm/resources/${collection.path_cover_l}?ts=${collection.updated_at}`
          : collection.name?.toLowerCase() == 'favourites'
            ? favoriteCoverImage
            : collectionCoverImage
      "
    >
      <template #error>
        <v-img :src="collectionCoverImage" />
      </template>
    </v-img>
  </v-avatar>
</template>
