<script setup lang="ts">
import { computed } from "vue";
import RelatedCard from "@/components/common/Game/Card/Related.vue";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const combined = computed(() => [
  ...(props.rom.igdb_metadata?.remakes ?? []),
  ...(props.rom.igdb_metadata?.remasters ?? []),
  ...(props.rom.igdb_metadata?.expanded_games ?? []),
]);
</script>
<template>
  <v-row no-gutters>
    <v-col
      v-for="game in combined"
      :key="game.id"
      cols="4"
      sm="3"
      md="6"
      class="pa-1"
    >
      <RelatedCard :game="game" />
    </v-col>
  </v-row>
</template>
