<script setup lang="ts">
import type { IGDBRelatedGame } from "@/__generated__";
import { useTheme } from "vuetify";

// Props
const props = defineProps<{
  rom: IGDBRelatedGame;
}>();
const emit = defineEmits(["click"]);
const handleClick = (event: MouseEvent) => {
  emit("click", { event: event, rom: props.rom });
};
const theme = useTheme();
</script>

<template>
  <v-card class="ma-1">
    <v-tooltip
      activator="parent"
      location="top"
      class="tooltip"
      transition="fade-transition"
      open-delay="1000"
      >{{ rom.name }}</v-tooltip
    >
    <v-img
      v-bind="props"
      :src="
        `${rom.cover_url}`
          ? `https:${rom.cover_url.replace('t_thumb', 't_cover_big')}`
          : `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
      "
      :aspect-ratio="2 / 3"
      cover
      lazy
      ><v-chip
        class="px-2 position-absolute chip-type text-white translucent-dark"
        density="compact"
        label
      >
        <span>
          {{ rom.type }}
        </span>
      </v-chip></v-img
    >
  </v-card>
</template>
<style scoped>
.chip-type {
  top: -0.1rem;
  left: -0.1rem;
}
</style>
