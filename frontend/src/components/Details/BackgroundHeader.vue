<script setup lang="ts">
import { useTheme } from "vuetify";
import type { RomSchema } from "@/__generated__";
const theme = useTheme();

const props = defineProps<{ rom: RomSchema }>();
const imgSrc = !props.rom.igdb_id && !props.rom.has_cover
  ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
  : !props.rom.has_cover
  ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
  : `/assets/romm/resources/${props.rom.path_cover_s}`;
const imgSrcLazy = !props.rom.igdb_id && !props.rom.has_cover
  ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
  : !props.rom.has_cover
  ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
  : `/assets/romm/resources/${props.rom.path_cover_s}`;
</script>

<template>
  <v-card rounded="0" flat>
    <v-img :src="imgSrc" :lazy-src="imgSrcLazy" cover />
  </v-card>
</template>

<style scoped>
.v-card {
  top: 0px;
  left: 0px;
  width: 100%;
  max-height: 330px;
}
.v-img {
  -webkit-filter: blur(15px);
  filter: blur(15px);
  transform: scale(1.05);
}
</style>
