<script setup lang="ts">
import type { IGDBRelatedGame } from "@/__generated__";
import { useTheme } from "vuetify";

// Props
const props = defineProps<{
  game: IGDBRelatedGame;
}>();
const theme = useTheme();
const handleClick = () => {
  if (props.game.slug) {
    window.open(
      `https://www.igdb.com/games/${props.game.slug}`,
      "_blank",
      "noopener noreferrer"
    );
  }
};
</script>

<template>
  <v-card class="ma-1" v-on:click="handleClick">
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
      :src="
        `${game.cover_url}`
          ? `https:${game.cover_url.replace('t_thumb', 't_cover_big')}`
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
          {{ game.type }}
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
