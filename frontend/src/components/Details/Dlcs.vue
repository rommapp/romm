<script setup lang="ts">
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="mb-3" no-gutters 
      v-for="expansion in rom.expansions">
    <v-img
      class="cover"
      :src="`https:${expansion.cover.url.replace('t_thumb', 't_cover_big')}`"
      :lazy-src="`https:${expansion.cover.url.replace('t_thumb', 't_cover_small')}`"
      :aspect-ratio="3 / 4"
    ></v-img>
    <v-col class="ml-3">
        <span>{{ expansion.name }}</span>
    </v-col>
  </v-row>
  <v-row class="mb-3" no-gutters 
      v-for="dlc in rom.dlcs">
    <v-img
      class="cover"
      :src="`https:${dlc.cover.url.replace('t_thumb', 't_cover_big')}`"
      :lazy-src="`https:${dlc.cover.url.replace('t_thumb', 't_cover_small')}`"
      :aspect-ratio="3 / 4"
    ></v-img>
    <v-col class="ml-3">
        <span>{{ dlc.name }}</span>
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
