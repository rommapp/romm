<script setup lang="ts">
// CoverArtPip — a small 2D box-art thumbnail floated in the bottom-right
// corner of a cover box, used when the main image is a screenshot (the
// continue-playing rail, the live-activity board) so the game stays
// identifiable. Renders the canonical GameCover forced to `cover_path`, so it
// resolves the rom's real cover (by `rom`) or an explicit cover URL (by
// `coverSrc`) — never 3D / physical / miximage.
//
// Positioning is `absolute`, so the host must give it a positioned ancestor:
// drop it into the GameCover default slot (GameCover's root is relative). The
// wrapper owns the footprint, rounding + lift; the host adds any hover fade.
import GameCover from "@/v2/components/shared/GameCover.vue";
import type { CoverArtRom } from "@/v2/composables/useCoverArt";

interface Props {
  /** The rom whose cover to resolve (gallery cards have the full rom). */
  rom?: CoverArtRom | null;
  /** Explicit cover URL, for surfaces that only have the path (activity). */
  coverSrc?: string | null;
  /** Alt / placeholder text for the inner cover. */
  title?: string;
  /** Webp override, forwarded to GameCover. */
  webp?: boolean;
}

withDefaults(defineProps<Props>(), {
  rom: null,
  coverSrc: undefined,
  title: "",
  webp: undefined,
});
</script>

<template>
  <div class="cover-art-pip" aria-hidden="true">
    <GameCover
      :rom="rom ?? null"
      :cover-src="coverSrc"
      :title="title"
      force-style="cover_path"
      :webp="webp"
    />
  </div>
</template>

<style scoped>
/* The wrapper owns the footprint, rounding + lift; `--r-cover-radius: 0`
   squares the inner GameCover so the wrapper's corners win. */
.cover-art-pip {
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 55px;
  z-index: 2;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  border: 1.5px solid var(--r-color-overlay-border);
  box-shadow: 0 2px 8px color-mix(in srgb, black 45%, transparent);
  pointer-events: none;
  --r-cover-radius: 0;
  transition: opacity 0.12s ease;
}
html[data-bp~="xs"] .cover-art-pip {
  width: 45px;
}
</style>
