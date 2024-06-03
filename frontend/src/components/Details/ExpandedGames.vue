<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom }>();
</script>
<template>
  <v-col
    v-for="game in rom.igdb_metadata?.expanded_games"
    :key="game.id"
    class="pa-0"
    cols="4"
    sm="2"
    md="3"
    lg="3"
  >
    <v-card class="ma-1">
      <v-img
        class="cover"
        :src="`https:${game.cover_url.replace('t_thumb', 't_cover_big')}`"
        :lazy-src="`https:${game.cover_url.replace(
          't_thumb',
          't_cover_small'
        )}`"
        :aspect-ratio="3 / 4"
      />
    </v-card>
  </v-col>
</template>
