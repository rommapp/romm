<script setup lang="ts">
import type { RomSchema } from "@/__generated__";
import { useTheme } from "vuetify";
const theme = useTheme();

const props = defineProps<{ rom: RomSchema }>();
const imgSrc =
  !props.rom.igdb_id && !props.rom.has_cover
    ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
    : !props.rom.has_cover
    ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
    : `/assets/romm/resources/${props.rom.path_cover_s}`;
const imgSrcLazy =
  !props.rom.igdb_id && !props.rom.has_cover
    ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
    : !props.rom.has_cover
    ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
    : `/assets/romm/resources/${props.rom.path_cover_s}`;
</script>

<template>
  <v-card rounded="0">
    <v-img :src="imgSrc" :lazy-src="imgSrcLazy" id="background-header" />
  </v-card>
</template>
<style scoped>
#background-header {
  width: 100%;
  height: 300px;
  transform: scale(7);
  filter: blur(8px);
}
</style>
