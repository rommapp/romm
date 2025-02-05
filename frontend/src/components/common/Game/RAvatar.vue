<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { computed } from "vue";

const props = withDefaults(defineProps<{ rom: SimpleRom; size?: number }>(), {
  size: 45,
});

const unmatchedCoverImage = computed(() =>
  getUnmatchedCoverImage(props.rom.name || props.rom.fs_name),
);
const missingCoverImage = computed(() =>
  getMissingCoverImage(props.rom.name || props.rom.fs_name),
);
</script>

<template>
  <v-avatar :width="size" rounded="0">
    <v-img
      :src="
        !rom.igdb_id && !rom.moby_id && !rom.has_cover
          ? unmatchedCoverImage
          : rom.has_cover
            ? `/assets/romm/resources/${rom.path_cover_s}?ts=${rom.updated_at}`
            : missingCoverImage
      "
    >
      <template #error>
        <v-img :src="missingCoverImage" />
      </template>
    </v-img>
  </v-avatar>
</template>
