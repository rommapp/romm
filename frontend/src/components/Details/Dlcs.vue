<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom }>();
</script>
<template>
  <v-row no-gutters>
    <v-col cols="4" sm="3" md="4" lg="6" xl="4" v-for="dlc in rom.igdb_metadata?.dlcs">
      <v-card class="ma-1">
        <v-img
          class="cover"
          :src="`https:${dlc.cover_url.replace('t_thumb', 't_cover_big')}`"
          :lazy-src="`https:${dlc.cover_url.replace(
            't_thumb',
            't_cover_small'
          )}`"
          :aspect-ratio="3 / 4"
        />
      </v-card>
    </v-col>
  </v-row>
</template>
