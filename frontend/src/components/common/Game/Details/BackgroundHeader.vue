<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import { useTheme } from "vuetify";

defineProps<{ rom: DetailedRom }>();
const theme = useTheme();
</script>

<template>
  <v-card rounded="0">
    <v-img
      id="background-header"
      :src="
        (!rom.igdb_id && !rom.moby_id) && !rom.has_cover
          ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      lazy
    >
      <template #error>
        <v-img
          :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
          :aspect-ratio="3 / 4"
        />
      </template>
      <template #placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular
            :width="2"
            :size="40"
            color="romm-accent-1"
            indeterminate
          />
        </div>
      </template>
    </v-img>
  </v-card>
</template>
<style scoped>
#background-header {
  width: 100%;
  height: 300px;
  transform: scale(10);
  filter: blur(5px);
}
</style>
