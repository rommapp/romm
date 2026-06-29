<script setup lang="ts">
// ArtworkSubtab — the Media tab's Artwork panel. A read-only gallery of every
// scraped art asset that doesn't already get its own surface (covers live on
// the page, screenshots have their own subtab, manual + soundtrack their own
// subtabs). Surfaces bezel / logo / marquee / box art / fan art / mix images /
// title screen plus the scraped videos, which the V2 GUI otherwise hid.
//
// Each asset is a labelled card. Images are contained (not cropped) since the
// set spans wildly different aspect ratios (wide marquees, tall box art) and
// open a fullscreen RCarousel lightbox on click. Videos play inline.
import { RCarousel, REmptyState, RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();

type ArtworkEntry = {
  key: string;
  label: string;
  url: string;
  isVideo: boolean;
};

// Asset definitions in display order. ScreenScraper is the richest source, so
// it wins; gamelist fills in for the few types it also scrapes (mirrors v1's
// MediaCarousel fallbacks).
function resolveArtwork(): ArtworkEntry[] {
  const ss = props.rom.ss_metadata;
  const gl = props.rom.gamelist_metadata;
  const cacheBust = encodeURIComponent(props.rom.updated_at);

  const defs: { key: string; label: string; path?: string | null }[] = [
    {
      key: "title_screen",
      label: t("rom.media-title-screen"),
      path: ss?.title_screen_path,
    },
    { key: "logo", label: t("rom.media-logo"), path: ss?.logo_path },
    {
      key: "marquee",
      label: t("rom.media-marquee"),
      path: ss?.marquee_path ?? gl?.marquee_path,
    },
    { key: "bezel", label: t("rom.media-bezel"), path: ss?.bezel_path },
    { key: "fanart", label: t("rom.media-fanart"), path: ss?.fanart_path },
    {
      key: "box3d",
      label: t("rom.media-box3d"),
      path: ss?.box3d_path ?? gl?.box3d_path,
    },
    {
      key: "box2d_back",
      label: t("rom.media-box2d-back"),
      path: ss?.box2d_back_path,
    },
    {
      key: "box2d_side",
      label: t("rom.media-box2d-side"),
      path: ss?.box2d_side_path,
    },
    {
      key: "physical",
      label: t("rom.media-physical"),
      path: ss?.physical_path ?? gl?.physical_path,
    },
    {
      key: "miximage",
      label: t("rom.media-miximage"),
      path: ss?.miximage_path ?? gl?.miximage_path,
    },
    {
      key: "miximage_v2",
      label: t("rom.media-miximage-v2"),
      path: ss?.miximage_v2_path,
    },
  ];

  const videos: { key: string; label: string; path?: string | null }[] = [
    { key: "video", label: t("rom.media-video"), path: props.rom.path_video },
    {
      key: "video_normalized",
      label: t("rom.media-video-normalized"),
      path: ss?.video_normalized_path,
    },
  ];

  const out: ArtworkEntry[] = [];
  const seen = new Set<string>();

  for (const def of defs) {
    if (!def.path || seen.has(def.path)) continue;
    seen.add(def.path);
    out.push({
      key: def.key,
      label: def.label,
      url: `${FRONTEND_RESOURCES_PATH}/${def.path}?v=${cacheBust}`,
      isVideo: false,
    });
  }
  for (const def of videos) {
    if (!def.path || seen.has(def.path)) continue;
    seen.add(def.path);
    out.push({
      key: def.key,
      label: def.label,
      url: `${FRONTEND_RESOURCES_PATH}/${def.path}?v=${cacheBust}`,
      isVideo: true,
    });
  }
  return out;
}

const artwork = computed(resolveArtwork);
const images = computed(() => artwork.value.filter((a) => !a.isVideo));

// Lightbox indexes into the image-only list, so map a clicked card to its
// position there (videos are skipped).
const lightboxIndex = ref(0);
const lightboxOpen = ref(false);

function openImage(entry: ArtworkEntry) {
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
        <img
          :src="(item as ArtworkEntry).url"
          :alt="(item as ArtworkEntry).label"
        />
      </template>
      <template #thumbnail="{ item }">
        <img
          :src="(item as ArtworkEntry).url"
          :alt="(item as ArtworkEntry).label"
        />
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
