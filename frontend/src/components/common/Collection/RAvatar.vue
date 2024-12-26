<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import { useTheme } from "vuetify";

withDefaults(defineProps<{ collection: Collection; size?: number }>(), {
  size: 45,
});
const theme = useTheme();
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img
      :src="
        collection.has_cover
          ? `/assets/romm/resources/${collection.path_cover_l}?ts=${collection.updated_at}`
          : collection.name?.toLowerCase() == 'favourites'
            ? `/assets/default/cover/small_${theme.global.name.value}_fav.png`
            : `/assets/default/cover/small_${theme.global.name.value}_collection.png`
      "
    >
      <template #error>
        <v-img
          :src="`assets/default/cover/big_${theme.global.name.value}_collection.png`"
        >
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
