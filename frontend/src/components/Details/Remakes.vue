<script setup lang="ts">
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="mt-2 mb-3" no-gutters v-for="remake in rom.remakes">
    <v-img
      class="cover"
      :src="`https:${remake.cover.url.replace('t_thumb', 't_cover_big')}`"
      :lazy-src="`https:${remake.cover.url.replace(
        't_thumb',
        't_cover_small'
      )}`"
      :aspect-ratio="3 / 4"
    ></v-img>
    <v-col class="ml-3">
      <span>{{ remake.name }}</span>
    </v-col>
  </v-row>
</template>

<style scoped>
.cover {
  min-width: 90px;
  min-height: 120px;
  max-width: 90px;
  max-height: 120px;
}
</style>
