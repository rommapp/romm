<script setup lang="ts">
// ArtworkSubtab: the Media tab's Artwork panel. A gallery of every art asset
// that doesn't already get its own surface (screenshots have their own
// subtab, manual + soundtrack their own subtabs). Surfaces the cover,
// bezel / logo / marquee / box art / fan art / mix images / title screen plus
// the scraped videos, and any image/video files sitting in the game folder
// in the library. Each can be pinned to the Overview tab.
import { REmptyState } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import MediaShelf from "@/v2/components/GameDetails/MediaShelf.vue";
import { usePinnedMedia } from "@/v2/composables/usePinnedMedia";
import { resolveRomArtwork } from "@/v2/utils/romArtwork";

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();
const { isPinned, togglePin } = usePinnedMedia(() => props.rom);

const artwork = computed(() => resolveRomArtwork(props.rom));
</script>

<template>
  <div class="r-v2-art">
    <REmptyState
      v-if="artwork.length === 0"
      icon="mdi-image-off-outline"
      :title="t('rom.artwork-empty')"
    />

    <MediaShelf
      v-else
      :items="artwork"
      captions
      :is-pinned="isPinned"
      @toggle-pin="togglePin"
    />
  </div>
</template>

<style scoped>
.r-v2-art {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  padding-right: 4px;
}
</style>
