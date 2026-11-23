<script setup lang="ts">
// ArtworkSubtab: the Media tab's Artwork panel, every art asset and video
// without a subtab of its own, each pinnable to the Overview tab.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import MediaShelf from "@/components/GameDetails/MediaShelf.vue";
import { usePinnedMedia } from "@/composables/usePinnedMedia";
import { REmptyState } from "@/lib";
import type { DetailedRom } from "@/stores/roms";
import { resolveRomArtwork } from "@/utils/romArtwork";

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();
const { isPinned, togglePin } = usePinnedMedia(() => props.rom);

const artwork = computed(() => resolveRomArtwork(props.rom));
</script>

<template>
  <div class="r-art">
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
.r-art {
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
