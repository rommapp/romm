<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import { useTheme } from "vuetify";

withDefaults(defineProps<{ collection: Collection; size?: number }>(), {
  size: 45,
});
const theme = useTheme();
</script>

<template>
  <v-avatar :size="size" rounded="0">
    <v-img
      :src="
        collection.has_cover
          ? `/assets/romm/resources/${collection.path_cover_l}?ts=${collection.updated_at}`
          : collection.name?.toLowerCase() == 'favourites'
            ? `/assets/default/cover/${theme.global.name.value}_fav.svg`
            : `/assets/default/cover/${theme.global.name.value}_collection.svg`
      "
    >
      <template #error>
        <v-img
          :src="`assets/default/cover/${theme.global.name.value}_collection.svg`"
        >
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
