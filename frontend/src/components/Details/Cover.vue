<script setup lang="ts">
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";
import { useTheme } from "vuetify";
const theme = useTheme();

const downloadStore = storeDownload();
const props = defineProps<{ rom: Rom }>();
console.log(props.rom)
</script>
<template>
  <v-card
    elevation="2"
    :loading="downloadStore.value.includes(rom.id) ? 'romm-accent-1' : false"
  >
    <v-img
      :src="
        !rom.has_cover
          ? `/assets/default/cover/big_${theme.global.name.value}.png`
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      :lazy-src="
        !rom.has_cover
          ? `/assets/default/cover/small_${theme.global.name.value}.png`
          : `/assets/romm/resources/${rom.path_cover_s}`
      "
      :aspect-ratio="3 / 4"
    >
      <!-- <span class="message">{{ rom.file_name }}</span> -->
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
.message {
    font-family: 'cassete';
    font-size: xx-large;
}
</style>