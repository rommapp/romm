<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import { useTheme } from "vuetify";

const props = withDefaults(defineProps<{ rom: SimpleRom; size?: number }>(), {
  size: 45,
});
const theme = useTheme();
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img
      :src="
        props.rom.path_cover_small ||
        `/assets/default/cover/small_${theme.global.name.value}_${props.rom.is_unidentified ? 'unmatched' : 'missing_cover'}.png`
      "
    >
      <template #error>
        <v-img
          :src="`assets/default/cover/big_${theme.global.name.value}_${props.rom.is_unidentified ? 'unmatched' : 'missing_cover'}.png`"
        >
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
