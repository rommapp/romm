<script setup lang="ts">
import RelatedCard from "@/components/common/Game/Card/Related.vue";
import type { DetailedRom } from "@/stores/roms";
import { computed } from "vue";

const props = defineProps<{ rom: DetailedRom }>();
const combined = computed(() => [
  ...(props.rom.igdb_metadata?.expansions ?? []),
  ...(props.rom.igdb_metadata?.dlcs ?? []),
]);
</script>
<template>
  <v-row no-gutters>
    <v-col
      cols="4"
      sm="3"
      md="3"
      lg="6"
      class="pa-1"
      v-for="expansion in combined"
    >
      <related-card :game="expansion" />
    </v-col>
  </v-row>
</template>
