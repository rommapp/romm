<script setup lang="ts">
import type { RomSchema } from "@/__generated__";
import { reactive } from "vue";
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

const style = reactive({
  width: "100%",
  height: "330px",
  "-webkit-filter": "blur(3px)",
  filter: "blur(3px)",
  transform: "scale(7)",
});
</script>

<template>
  <v-card>
    <v-img :src="imgSrc" :lazy-src="imgSrcLazy" :style="style" />
  </v-card>
</template>
