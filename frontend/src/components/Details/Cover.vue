<script setup lang="ts">
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";
import { useTheme } from "vuetify";
const theme = useTheme();

const downloadStore = storeDownload();
defineProps<{ rom: Rom; editable: boolean }>();
</script>
<template>
  <v-card
    elevation="2"
    :loading="downloadStore.value.includes(rom.id) ? 'romm-accent-1' : false"
  >
    <v-img
      :value="rom.id"
      :key="rom.id"
      :src="
        !rom.igdb_id && !rom.has_cover
          ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
          : !rom.has_cover
          ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      :lazy-src="
        !rom.igdb_id && !rom.has_cover
          ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
          : !rom.has_cover
          ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
          : `/assets/romm/resources/${rom.path_cover_s}`
      "
      :aspect-ratio="3 / 4"
    >
      <v-chip-group v-if="editable" class="position-absolute edit-cover pa-0">
        <v-chip class="translucent" size="small" @click="" label
          ><v-icon>mdi-pencil</v-icon></v-chip
        >
        <v-chip class="translucent" size="small" @click="" label
          ><v-icon class="text-red">mdi-delete</v-icon></v-chip
        >
      </v-chip-group>
      <template v-slot:placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular
            color="romm-accent-1"
            :width="2"
            :size="20"
            indeterminate
          />
        </div>
      </template>
    </v-img>
  </v-card>
</template>

<style scoped>
.edit-cover {
  bottom: -0.1rem;
  right: -0.1rem;
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}
</style>
