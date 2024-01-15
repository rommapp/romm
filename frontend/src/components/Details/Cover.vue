<script setup lang="ts">
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";

const downloadStore = storeDownload();
defineProps<{ rom: Rom }>();
</script>
<template>
  <v-card
    elevation="2"
    :loading="downloadStore.value.includes(rom.id) ? 'romm-accent-1' : false"
  >
    <v-img
      :cover="!rom.has_cover"
      :src="
        !rom.has_cover && rom.merged_screenshots.length > 0
          ? rom.merged_screenshots[0]
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      :lazy-src="`/assets/romm/resources/${rom.path_cover_s}`"
      :aspect-ratio="3 / 4"
    >
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
