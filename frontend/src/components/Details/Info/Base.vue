<script setup lang="ts">
import type { EnhancedRomSchema, PlatformSchema } from "@/__generated__";
import FileInfo from "@/components/Details/Info/FileInfo";
import GameInfo from "@/components/Details/Info/GameInfo";
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import storeDownload from "@/stores/download";
import { formatBytes } from "@/utils";
import { useDisplay } from "vuetify";

defineProps<{ rom: EnhancedRomSchema; platform: PlatformSchema }>();
const downloadStore = storeDownload();
const { xs } = useDisplay();
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
