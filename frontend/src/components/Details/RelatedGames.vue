<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import { ref } from "vue";

const props = defineProps<{ rom: DetailedRom }>();
const combined = ref([
  ...(props.rom.igdb_metadata?.remakes ?? []),
  ...(props.rom.igdb_metadata?.remasters ?? []),
  ...(props.rom.igdb_metadata?.expanded_games ?? []),
]);
import { useTheme } from "vuetify";
const theme = useTheme();
</script>
<template>
  <v-row no-gutters>
    <v-col
      v-for="game in combined"
      :key="game.id"
      class="pa-0"
      cols="4"
      sm="3"
      md="6"
      lg="6"
      xl="6"
    >
      <v-card class="ma-1">
        <v-tooltip
          activator="parent"
          location="top"
          class="tooltip"
          transition="fade-transition"
          open-delay="1000"
        >
          {{ game.name }}
        </v-tooltip>
        <v-img
          v-bind="props"
          class="cover"
          :src="
            `${game.cover_url}`
              ? `https:${game.cover_url.replace('t_thumb', 't_cover_big')}`
              : `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
          "
          :aspect-ratio="3 / 4"
          lazy
        >
          <v-chip
            class="px-2 position-absolute chip-type text-white translucent"
            density="compact"
            label
          >
            <span>
              {{ game.type }}
            </span>
          </v-chip>
        </v-img>
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
