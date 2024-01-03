<script setup lang="ts">
import type { Rom } from '@/stores/roms';

defineProps<{ rom: Rom }>();
</script>
<template>
  <v-row class="d-flex mt-2" no-gutters>
    <v-carousel
      hide-delimiter-background
      delimiter-icon="mdi-square"
      class="bg-romm-black"
      show-arrows="hover"
      height="400"
    >
      <v-carousel-item
        v-for="screenshot in rom.path_screenshots"
        :src="`/assets/romm/resources/${screenshot}`"
      />
    </v-carousel>
  </v-row>
</template>
