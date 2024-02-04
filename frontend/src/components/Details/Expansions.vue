<script setup lang="ts">
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row no-gutters>
    <v-col cols="4" sm="3" md="4" lg="6" xl="4" v-for="expansion in rom.expansions">
      <v-card class="ma-1">
        <v-img
          class="cover"
          :src="`https:${expansion.cover.url.replace(
            't_thumb',
            't_cover_big'
          )}`"
          :lazy-src="`https:${expansion.cover.url.replace(
            't_thumb',
            't_cover_small'
          )}`"
          :aspect-ratio="3 / 4"
        />
      </v-card>
    </v-col>
  </v-row>
</template>
