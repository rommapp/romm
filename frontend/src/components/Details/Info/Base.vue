<script setup lang="ts">
import type { PlatformSchema } from "@/__generated__";
import FileInfo from "@/components/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Details/Info/GameInfo.vue";
import type { DetailedRom } from "@/stores/roms";

defineProps<{ rom: DetailedRom; platform: PlatformSchema }>();
</script>
<template>
  <file-info :rom="rom" :platform="platform" />
  <game-info :rom="rom" />
</template>
<style scoped>
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(2px);
}
</style>
