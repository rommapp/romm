<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom }>();
</script>
<template>
  <div />
  <!-- TODO: user screenshots -->
  <!-- <v-carousel
    hide-delimiter-background
    delimiter-icon="mdi-square"
    class="bg-romm-black"
    show-arrows="hover"
    :height="xs ? '200' : '350'"
  >
    <v-carousel-item
      v-for="screenshot_url in rom.user_screenshots"
      :src="screenshot_url"
    />
  </v-carousel> -->
</template>
