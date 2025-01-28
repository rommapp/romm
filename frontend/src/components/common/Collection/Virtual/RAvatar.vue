<script setup lang="ts">
import type { VirtualCollection } from "@/stores/collections";
import { useTheme } from "vuetify";

withDefaults(defineProps<{ collection: VirtualCollection; size?: number }>(), {
  size: 45,
});
const theme = useTheme();
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img :src="collection.path_covers_large[0]">
      <template #error>
        <v-img
          :src="`assets/default/cover/big_${theme.global.name.value}_collection.png`"
        >
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
