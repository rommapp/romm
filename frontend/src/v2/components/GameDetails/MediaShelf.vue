<script setup lang="ts">
// MediaShelf: mixed-shape art (a box spine next to a 16:9 screenshot) on a
// shared baseline, each asset keeping its own proportions.
import { RCarousel, RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import MediaPinBtn from "@/v2/components/GameDetails/MediaPinBtn.vue";

export type MediaShelfItem = {
  key: string;
  label: string;
  url: string;
  isVideo?: boolean;
};

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  items: MediaShelfItem[];
  captions?: boolean;
  compact?: boolean;
  isPinned?: (key: string) => boolean;
}>();
const emit = defineEmits<{ "toggle-pin": [key: string] }>();

const { t } = useI18n();

const images = computed(() => props.items.filter((item) => !item.isVideo));

// Lightbox indexes into the image-only list, so map a clicked card to its
// position there (videos are skipped).
const lightboxIndex = ref(0);
const lightboxOpen = ref(false);

function openImage(item: MediaShelfItem) {
  const idx = images.value.findIndex((image) => image.key === item.key);
  if (idx === -1) return;
  lightboxIndex.value = idx;
  lightboxOpen.value = true;
}
function close() {
  lightboxOpen.value = false;
}
</script>

<template>
  <section
    v-bind="$attrs"
    class="r-v2-media-shelf"
    :class="{ 'r-v2-media-shelf--compact': compact }"
  >
    <figure
      v-for="(item, i) in items"
      :key="item.key"
      class="r-v2-media-shelf__cell r-v2-asset-fade"
      :style="{ '--asset-fade-i': i }"
    >
      <div class="r-v2-media-shelf__frame">
        <div class="r-v2-media-shelf__stage">
          <!-- Scraped preview clips ship no caption track. -->
          <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
          <video
            v-if="item.isVideo"
            class="r-v2-media-shelf__media r-v2-media-shelf__media--video"
            :src="item.url"
            controls
            preload="metadata"
          />
          <button
            v-else
            type="button"
            class="r-v2-media-shelf__btn"
            :aria-label="t('rom.artwork-open', { name: item.label })"
            @click="openImage(item)"
          >
            <img
              class="r-v2-media-shelf__media"
              :src="item.url"
              :alt="item.label"
              loading="lazy"
            />
          </button>
          <MediaPinBtn
            v-if="isPinned"
            class="r-v2-media-shelf__pin"
            :pinned="isPinned(item.key)"
            @toggle="emit('toggle-pin', item.key)"
          />
        </div>
      </div>
      <figcaption v-if="captions" class="r-v2-media-shelf__caption">
        <RIcon v-if="item.isVideo" icon="mdi-play-circle-outline" size="13" />
        {{ item.label }}
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
</template>

<style scoped>
.r-v2-media-shelf {
  /* Shared cap on every asset's height and width. */
  --art-h: 232px;
  --art-w: min(28rem, calc(100vw - 4rem));
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 28px 26px;
  padding: 10px 2px 6px;
}
.r-v2-media-shelf--compact {
  --art-h: 168px;
  gap: 20px 18px;
}

/* Never shrink: a squeezed cell would keep the fixed frame height while
   narrowing the asset, so the box would stop matching the artwork's shape. */
.r-v2-media-shelf__cell {
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
.r-v2-media-shelf__frame {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  height: var(--art-h);
}

/* Shrink-wraps the asset so the pin sits on its corner, not the frame's. */
.r-v2-media-shelf__stage {
  position: relative;
}

.r-v2-media-shelf__btn {
  appearance: none;
  display: block;
  border: 0;
  padding: 0;
  cursor: pointer;
  background: transparent;
  border-radius: var(--r-radius-art);
}

.r-v2-media-shelf__media {
  display: block;
  width: auto;
  height: auto;
  max-width: var(--art-w);
  max-height: var(--art-h);
  border-radius: var(--r-radius-art);
  /* drop-shadow follows the silhouette of transparent PNGs (boxes, logos). */
  filter: drop-shadow(0 12px 20px color-mix(in srgb, black 45%, transparent));
  transition:
    transform var(--r-motion-med) var(--r-motion-ease-out),
    filter var(--r-motion-med) var(--r-motion-ease-out);
}

/* Free width tracks the clip's ratio once metadata lands; the backing only
   covers the wait before then. */
.r-v2-media-shelf__media--video {
  height: var(--art-h);
  background: var(--r-color-cover-placeholder);
}

.r-v2-media-shelf__btn:hover .r-v2-media-shelf__media {
  transform: translateY(-6px);
  filter: drop-shadow(0 22px 28px color-mix(in srgb, black 60%, transparent));
}
.r-v2-media-shelf__btn:active .r-v2-media-shelf__media {
  transform: translateY(-2px);
}

.r-v2-media-shelf__pin {
  position: absolute;
  top: 6px;
  right: 6px;
  opacity: 0;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-media-shelf__cell:hover .r-v2-media-shelf__pin,
.r-v2-media-shelf__cell:focus-within .r-v2-media-shelf__pin {
  opacity: 1;
}
/* No hover to reveal it with at phone and tablet widths. */
html[data-bp~="sm-and-down"] .r-v2-media-shelf__pin {
  opacity: 1;
}

.r-v2-media-shelf__caption {
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
.r-v2-media-shelf__cell:hover .r-v2-media-shelf__caption {
  color: var(--r-color-fg-secondary);
}

html[data-bp~="sm-and-down"] .r-v2-media-shelf {
  --art-h: 168px;
  gap: 22px 18px;
}
html[data-bp~="sm-and-down"] .r-v2-media-shelf--compact {
  --art-h: 128px;
}
</style>
