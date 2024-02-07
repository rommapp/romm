<script setup lang="ts">
import type { EnhancedRomSchema, PlatformSchema } from "@/__generated__";
import FileInfo from "@/components/Details/Info/FileInfo.vue";
import GameInfo from "@/components/Details/Info/GameInfo.vue";
import storeDownload from "@/stores/download";
import { useDisplay } from "vuetify";

defineProps<{ rom: EnhancedRomSchema; platform: PlatformSchema }>();
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
