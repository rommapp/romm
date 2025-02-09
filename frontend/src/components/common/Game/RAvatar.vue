<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { computed } from "vue";

const props = withDefaults(defineProps<{ rom: SimpleRom; size?: number }>(), {
  size: 45,
});

const fallbackCoverImage = computed(() =>
  props.rom.igdb_id || props.rom.moby_id ? getMissingCoverImage(props.rom.name || props.rom.fs_name) : getUnmatchedCoverImage(props.rom.name || props.rom.fs_name),
);
</script>

<template>
  <v-avatar :width="size" rounded="0">
    <v-img
      :src="props.rom.path_cover_small || fallbackCoverImage"
    >
      <template #error>
        <v-img :src="fallbackCoverImage" />
      </template>
    </v-img>
  </v-avatar>
</template>
