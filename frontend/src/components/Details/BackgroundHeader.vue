<script setup lang="ts">
import type { RomSchema } from "../../__generated__/";
import { useTheme } from "vuetify";
const theme = useTheme();

defineProps<{ rom: RomSchema }>();
</script>

<template>
  <v-card id="header-background" rounded="0">
      <v-img
        :src="
          !rom.has_cover
            ? `/assets/romm/resources/default/default/cover/small_${theme.global.name.value}.png`
            : `/assets/romm/resources/${rom.path_cover_s}`
        "
        id="header-background-img"
        cover
      />
  </v-card>
</template>

<style scoped>
#header-background {
  top: 0px;
  left: 0px;
  width: 100%;
  max-height: 330px;
}
#header-background-img {
  -webkit-filter: blur(15px);
  filter: blur(15px);
  transform: scale(1.05);
}
</style>
