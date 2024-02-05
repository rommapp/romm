<script setup lang="ts">
import type { Rom } from "@/stores/roms";
import { onMounted, ref } from "vue";

const props = defineProps<{ rom: Rom }>();
const combined = ref();
onMounted(() => {
  props.rom.remakes.forEach((rom) => {
    rom.type = "remake";
  });
  props.rom.remasters.forEach((rom) => {
    rom.type = "remaster";
  });
  props.rom.expanded_games.forEach((rom) => {
    rom.type = "expanded";
  });
  combined.value = [
    ...props.rom.remakes,
    ...props.rom.remasters,
    ...props.rom.expanded_games,
  ];
});
</script>
<template>
  <v-row no-gutters>
    <v-col
      class="pa-0"
      cols="4"
      sm="3"
      md="6"
      lg="6"
      xl="6"
      v-for="game in combined"
    >
      <v-card class="ma-1">
        <v-tooltip
          activator="parent"
          location="top"
          class="tooltip"
          transition="fade-transition"
          open-delay="1000"
          >{{ game.name }}</v-tooltip
        >
        <v-img
          v-bind="props"
          class="cover"
          :src="`https:${game.cover.url.replace('t_thumb', 't_cover_big')}`"
          :lazy-src="`https:${game.cover.url.replace(
            't_thumb',
            't_cover_small'
          )}`"
          :aspect-ratio="3 / 4"
          ><v-chip
            class="px-2 position-absolute chip-type text-white translucent"
            density="compact"
            label
          >
            <span>
              {{ game.type }}
            </span>
          </v-chip></v-img
        >
      </v-card>
    </v-col>
  </v-row>
</template>
<style scoped>
.chip-type {
  top: -0.1rem;
  left: -0.1rem;
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
}
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
