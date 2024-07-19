<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import { useTheme } from "vuetify";

withDefaults(defineProps<{ rom: SimpleRom; size?: number }>(), { size: 45 });
const theme = useTheme();
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img
      :src="
        !rom.igdb_id && !rom.moby_id && !rom.has_cover
          ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
          : rom.has_cover
          ? `/assets/romm/resources/${rom.path_cover_s}?ts=${rom.updated_at}`
          : `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
      "
    />
  </v-avatar>
</template>
