<script setup lang="ts">
const props = defineProps(["rom"]);
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
