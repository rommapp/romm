<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom }>();
</script>
<template>
  <v-row
    class="mb-3"
    no-gutters
  >
    <v-col
      v-for="remaster in rom.igdb_metadata?.remasters"
      :key="remaster.id"
      cols="4"
      sm="2"
      md="3"
      lg="3"
    >
      <v-card class="ma-1">
        <v-img
          class="cover"
          :src="`https:${remaster.cover_url.replace('t_thumb', 't_cover_big')}`"
          :lazy-src="`https:${remaster.cover_url.replace(
            't_thumb',
            't_cover_small'
          )}`"
          :aspect-ratio="3 / 4"
        />
      </v-card>
    </v-col>
  </v-row>
</template>
