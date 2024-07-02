<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import { useTheme } from "vuetify";

defineProps<{ collection: Collection }>();
const theme = useTheme();
</script>

<template>
  <v-img
    :aspect-ratio="2 / 3"
    :src="
      collection.path_cover_l ??
      `/assets/default/cover/big_${theme.global.name.value}_empty.png`
    "
    :lazy-src="
      collection.path_cover_s ??
      `/assets/default/cover/small_${theme.global.name.value}_empty.png`
    "
    cover
  >
    <template #error>
      <v-img
        :aspect-ratio="2 / 3"
        :src="`assets/default/cover/big_${theme.global.name.value}_empty.png`"
        cover
      >
      </v-img>
    </template>
  </v-img>
</template>
