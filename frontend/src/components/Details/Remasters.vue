<script setup lang="ts">
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="mb-3" no-gutters>
    <v-col cols="4" sm="2" md="3" lg="3" v-for="remaster in rom.igdb_metadata?.remasters">
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
