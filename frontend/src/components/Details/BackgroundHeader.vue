<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import { useTheme } from "vuetify";
const theme = useTheme();

const props = defineProps<{ rom: DetailedRom }>();
</script>

<template>
  <v-card rounded="0">
    <v-img
      :src="
        !rom.igdb_id && !rom.moby_id
          ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      id="background-header"
      lazy
    >
      <template v-slot:error>
        <v-img
          :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
          :aspect-ratio="3 / 4"
        ></v-img>
      </template>
      <template v-slot:placeholder>
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
  transform: scale(7);
  filter: blur(8px);
}
</style>
