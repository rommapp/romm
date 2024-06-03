<script setup lang="ts">
import FileInfo from "@/components/Game/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Game/Details/Info/GameInfo.vue";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom; platform: Platform }>();
</script>
<template>
  <file-info
    :rom="rom"
    :platform="platform"
  />
  <game-info :rom="rom" />
</template>
