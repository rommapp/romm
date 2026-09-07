<script setup lang="ts">
// ArtworkSubtab — the Media tab's Artwork panel. A read-only gallery of every
// art asset that doesn't already get its own surface (screenshots have their
// own subtab, manual + soundtrack their own subtabs). Surfaces the cover,
// bezel / logo / marquee / box art / fan art / mix images / title screen plus
// the scraped videos, which the V2 GUI otherwise hid, and any image/video
// files sitting in the game folder in the library.
//
// The set spans wildly different shapes (a 42x680 box spine next to a 16:9
// title screen), so the layout is a shelf rather than a grid: each asset keeps
// its real proportions, capped to a shared height, and stands on a common
// baseline. Images open a fullscreen RCarousel lightbox on click; videos play
// inline.
import { RCarousel, REmptyState, RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import { resolveRomArtwork, type RomArtworkEntry } from "@/v2/utils/romArtwork";

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();

const artwork = computed(() => resolveRomArtwork(props.rom));
const images = computed(() => artwork.value.filter((a) => !a.isVideo));

// Lightbox indexes into the image-only list, so map a clicked card to its
// position there (videos are skipped).
const lightboxIndex = ref(0);
const lightboxOpen = ref(false);

function openImage(entry: RomArtworkEntry) {
  const idx = images.value.findIndex((a) => a.key === entry.key);
  if (idx === -1) return;
  lightboxIndex.value = idx;
  lightboxOpen.value = true;
}
function close() {
  lightboxOpen.value = false;
}
</script>

<template>
  <div class="r-v2-art">
    <REmptyState
      v-if="artwork.length === 0"
      icon="mdi-image-off-outline"
      :title="t('rom.artwork-empty')"
    />

    <section v-else class="r-v2-art__shelf">
      <figure
        v-for="(entry, i) in artwork"
        :key="entry.key"
        class="r-v2-art__cell r-v2-asset-fade"
        :style="{ '--asset-fade-i': i }"
      >
        <div class="r-v2-art__frame">
          <!-- Scraped preview clips ship no caption track. -->
          <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
          <video
            v-if="entry.isVideo"
            class="r-v2-art__media r-v2-art__media--video"
            :src="entry.url"
            controls
            preload="metadata"
          />
          <button
            v-else
            type="button"
            class="r-v2-art__btn"
            :aria-label="t('rom.artwork-open', { name: entry.label })"
            @click="openImage(entry)"
          >
            <img
              class="r-v2-art__media"
              :src="entry.url"
              :alt="entry.label"
              loading="lazy"
            />
          </button>
        </div>
        <figcaption class="r-v2-art__caption">
          <RIcon
            v-if="entry.isVideo"
            icon="mdi-play-circle-outline"
            size="13"
          />
          {{ entry.label }}
        </figcaption>
      </figure>
    </section>

    <RCarousel
      v-if="lightboxOpen"
      v-model="lightboxIndex"
      :items="images"
      fullscreen
      show-thumbnails
      :aria-label="t('rom.artwork')"
      @close="close"
    >
      <template #default="{ item }">
        <img :src="item.url" :alt="item.label" />
      </template>
      <template #thumbnail="{ item }">
        <img :src="item.url" :alt="item.label" />
      </template>
    </RCarousel>
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

.r-v2-art__shelf {
  /* Shared cap every asset is measured against: the tallest it may stand and
     the widest it may run. */
  --art-h: 232px;
  --art-w: min(28rem, calc(100vw - 4rem));
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 28px 26px;
  padding: 10px 2px 6px;
}

/* Never shrink: a squeezed cell would keep the fixed frame height while
   narrowing the asset, so the box would stop matching the artwork's shape. */
.r-v2-art__cell {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin: 0;
  max-width: var(--art-w);
}

/* Fixed height, bottom-aligned: rows hold their shape while lazy images
   arrive, and every asset lands on the same baseline whatever its shape. */
.r-v2-art__frame {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  height: var(--art-h);
}

.r-v2-art__btn {
  appearance: none;
  display: block;
  border: 0;
  padding: 0;
  cursor: pointer;
  background: transparent;
  border-radius: var(--r-radius-art);
}

.r-v2-art__media {
  display: block;
  width: auto;
  height: auto;
  max-width: var(--art-w);
  max-height: var(--art-h);
  border-radius: var(--r-radius-art);
  /* drop-shadow, not box-shadow: most of these scans are transparent PNGs
     (3D boxes, logos, marquees), so the shadow follows the artwork's own
     silhouette instead of outlining an invisible rectangle. */
  filter: drop-shadow(0 12px 20px color-mix(in srgb, black 45%, transparent));
  transition:
    transform var(--r-motion-med) var(--r-motion-ease-out),
    filter var(--r-motion-med) var(--r-motion-ease-out);
}

/* Height-pinned with a free width, so the element tracks the clip's own
   ratio once metadata lands and the backing never shows as side bars. The
   backing only covers the wait, since a video carries no intrinsic size
   until then. */
.r-v2-art__media--video {
  height: var(--art-h);
  background: var(--r-color-cover-placeholder);
}

.r-v2-art__btn:hover .r-v2-art__media {
  transform: translateY(-6px);
  filter: drop-shadow(0 22px 28px color-mix(in srgb, black 60%, transparent));
}
.r-v2-art__btn:active .r-v2-art__media {
  transform: translateY(-2px);
}

.r-v2-art__caption {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-align: center;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-art__cell:hover .r-v2-art__caption {
  color: var(--r-color-fg-secondary);
}

html[data-bp~="sm-and-down"] .r-v2-art__shelf {
  --art-h: 168px;
  gap: 22px 18px;
}
</style>
