<script setup lang="ts">
import type { Rom } from "@/stores/roms";
import ActionBar from "../Game/Card/ActionBar.vue";

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="mb-3" no-gutters>
    <v-col cols="4" sm="2" md="3" lg="6" v-for="dlc in rom.dlcs">
      <v-card class="ma-1">
        <v-img
          class="cover"
          :src="`https:${dlc.cover.url.replace('t_thumb', 't_cover_big')}`"
          :lazy-src="`https:${dlc.cover.url.replace(
            't_thumb',
            't_cover_small'
          )}`"
          :aspect-ratio="3 / 4"
        />
        <!-- <action-bar :rom="rom" /> -->
      </v-card>
    </v-col>
  </v-row>
</template>
