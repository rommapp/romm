<script setup lang="ts">
// ArtworkSubtab — the Media tab's Artwork panel. A read-only gallery of every
// art asset that doesn't already get its own surface (covers live on the page,
// screenshots have their own subtab, manual + soundtrack their own subtabs).
// Surfaces bezel / logo / marquee / box art / fan art / mix images / title
// screen plus the scraped videos, which the V2 GUI otherwise hid, and any
// image/video files sitting in the game folder in the library.
//
// Each asset is a labelled card. Images are contained (not cropped) since the
// set spans wildly different aspect ratios (wide marquees, tall box art) and
// open a fullscreen RCarousel lightbox on click. Videos play inline.
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

    <section v-else class="r-v2-art__grid">
      <figure
        v-for="(entry, i) in artwork"
        :key="entry.key"
        class="r-v2-art__cell r-v2-asset-fade"
        :style="{ '--asset-fade-i': i }"
      >
        <!-- Scraped preview clips ship no caption track. -->
        <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
        <video
          v-if="entry.isVideo"
          class="r-v2-art__media"
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
        <figcaption class="r-v2-art__caption">
          <RIcon
            :icon="
              entry.isVideo ? 'mdi-play-circle-outline' : 'mdi-image-outline'
            "
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

.r-v2-art__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  padding: 6px 2px 4px;
}

.r-v2-art__cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.r-v2-art__btn {
  appearance: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  background: transparent;
  border-radius: var(--r-radius-md);
}

.r-v2-art__media {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: contain;
  border-radius: var(--r-radius-md);
  background: var(--r-color-cover-placeholder);
  border: 1px solid var(--r-color-border);
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-art__btn:hover .r-v2-art__media {
  transform: scale(1.02);
  box-shadow: 0 8px 24px color-mix(in srgb, black 35%, transparent);
}
.r-v2-art__btn:active .r-v2-art__media {
  transform: scale(0.99);
}

.r-v2-art__caption {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}
</style>
