<script setup lang="ts">
import RelatedCard from "@/components/common/Game/Card/Related.vue";
import type { DetailedRom } from "@/stores/roms";
import { ref } from "vue";

const props = defineProps<{ rom: DetailedRom }>();
const combined = ref([
  ...(props.rom.igdb_metadata?.expansions ?? []),
  ...(props.rom.igdb_metadata?.dlcs ?? []),
]);
</script>
<template>
  <v-row no-gutters>
    <v-col
      class="pa-0"
      cols="4"
      sm="3"
      lg="6"
      xxl="4"
      v-for="expansion in combined"
    >
      <a
        style="text-decoration: none; color: inherit"
        :href="`https://www.igdb.com/games/${expansion.slug}`"
        target="_blank"
      >
        <related-card :game="expansion" />
      </a>
    </v-col>
  </v-row>
</template>
<style scoped>
.chip-type {
  top: -0.1rem;
  left: -0.1rem;
}
</style>
