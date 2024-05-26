<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
import { useTheme } from "vuetify";
const theme = useTheme();
</script>
<template>
  <v-row no-gutters>
    <v-col
      class="pa-0"
      cols="4"
      sm="3"
      md="3"
      lg="4"
      xl="6"
      v-for="expansion in rom.igdb_metadata?.expansions"
    >
      <a
        style="text-decoration: none; color: inherit"
        :href="`https://www.igdb.com/games/${expansion.slug}`"
        target="_blank"
      >
        <v-card class="ma-1">
          <v-tooltip
            activator="parent"
            location="top"
            class="tooltip"
            transition="fade-transition"
            open-delay="1000"
            >{{ expansion.name }}</v-tooltip
          >
          <v-img
            v-bind="props"
            class="cover"
            :src="
              `${expansion.cover_url}`
                ? `https:${expansion.cover_url.replace(
                    't_thumb',
                    't_cover_big'
                  )}`
                : `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
            "
            :lazy-src="
              `${expansion.cover_url}`
                ? `https:${expansion.cover_url.replace(
                    't_thumb',
                    't_cover_big'
                  )}`
                : `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
            "
            :aspect-ratio="3 / 4"
            ><v-chip
              class="px-2 position-absolute chip-type text-white translucent"
              density="compact"
              label
            >
              <span>expansion</span>
            </v-chip></v-img
          >
        </v-card>
      </a>
    </v-col>
  </v-row>
  <v-row no-gutters>
    <v-col
      class="pa-0"
      cols="4"
      sm="3"
      md="3"
      lg="4"
      xl="6"
      v-for="dlc in rom.igdb_metadata?.dlcs"
    >
      <a
        style="text-decoration: none; color: inherit"
        :href="`https://www.igdb.com/games/${dlc.slug}`"
        target="_blank"
      >
        <v-card class="ma-1">
          <v-tooltip
            activator="parent"
            location="top"
            class="tooltip"
            transition="fade-transition"
            open-delay="1000"
            >{{ dlc.name }}</v-tooltip
          >
          <v-img
            v-bind="props"
            class="cover"
            :src="
              `${dlc.cover_url}`
                ? `https:${dlc.cover_url.replace('t_thumb', 't_cover_big')}`
                : `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
            "
            :lazy-src="
              `${dlc.cover_url}`
                ? `https:${dlc.cover_url.replace('t_thumb', 't_cover_small')}`
                : `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
            "
            :aspect-ratio="3 / 4"
            ><v-chip
              class="px-2 position-absolute chip-type text-white translucent"
              density="compact"
              label
            >
              <span>dlc</span>
            </v-chip></v-img
          >
        </v-card>
      </a>
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
