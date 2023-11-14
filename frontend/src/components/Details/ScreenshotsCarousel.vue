<script setup>
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
        v-for="screenshot_url in rom.merged_screenshost"
        :src="screenshot_url"
      />
    </v-carousel>
  </v-row>
</template>
