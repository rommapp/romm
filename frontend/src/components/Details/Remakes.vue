<script setup lang="ts">
import type { Rom } from "@/stores/roms";
import ActionBar from "../Game/Card/ActionBar.vue";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="mb-3" no-gutters v-for="remake in rom.remakes">
    <v-col cols="3" lg="4" v-for="remake in rom.remakes">
      <v-card class="ma-2">
    <v-img
      class="cover"
      :src="`https:${remake.cover.url.replace('t_thumb', 't_cover_big')}`"
      :lazy-src="`https:${remake.cover.url.replace(
        't_thumb',
        't_cover_small'
      )}`"
      :aspect-ratio="3 / 4"
    />
    <action-bar :rom="rom" />
    </v-card>
    </v-col>
    <!-- <v-col class="ml-3">
      <span class="text-caption">{{ remake.name }}</span>
    </v-col> -->
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
