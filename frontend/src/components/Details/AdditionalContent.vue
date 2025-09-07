<script setup lang="ts">
import { computed } from "vue";
import RelatedCard from "@/components/common/Game/Card/Related.vue";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{ rom: DetailedRom }>();
const combined = computed(() => [
  ...(props.rom.igdb_metadata?.expansions ?? []),
  ...(props.rom.igdb_metadata?.dlcs ?? []),
]);
</script>
<template>
  <v-row no-gutters>
    <v-col
      v-for="expansion in combined"
      :key="expansion.id"
      cols="4"
      sm="3"
      lg="6"
      class="pa-1"
    >
      <RelatedCard :game="expansion" />
    </v-col>
  </v-row>
</template>
