<script setup lang="ts">
import { computed, useTemplateRef } from "vue";
import type { VImg } from "vuetify/lib/components/VImg/VImg.js";
import { useGameAnimation } from "@/composables/useGameAnimation";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import {
  EXTENSION_REGEX,
  getMissingCoverImage,
  getUnmatchedCoverImage,
} from "@/utils/covers";

const props = withDefaults(defineProps<{ rom: SimpleRom; size?: number }>(), {
  size: 45,
});

const heartbeatStore = storeHeartbeat();
const coverRef = useTemplateRef<VImg>("game-image-ref");

const isWebpEnabled = computed(
  () => heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
);

const { boxartStyleCover } = useGameAnimation({
  rom: props.rom,
  isHovering: computed(() => false),
  coverRef: coverRef,
});

const smallCover = computed(() => {
  if (boxartStyleCover.value)
    return `${FRONTEND_RESOURCES_PATH}/${boxartStyleCover.value}`;
  const pathCoverSmall = isWebpEnabled.value
    ? props.rom.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_small;
  return pathCoverSmall || "";
});

const fallbackCoverImage = computed(() =>
  props.rom.is_identified
    ? getMissingCoverImage(props.rom.name || props.rom.fs_name)
    : getUnmatchedCoverImage(props.rom.name || props.rom.fs_name),
);
</script>

<template>
  <v-avatar variant="text" :width="size" rounded="0">
    <v-img
      eager
      ref="game-image-ref"
      :src="smallCover || fallbackCoverImage"
      :cover="!boxartStyleCover"
      :contain="boxartStyleCover"
    >
      <template #placeholder>
        <Skeleton :platform-id="rom.platform_id" type="image" />
      </template>
    </v-img>
  </v-avatar>
</template>
