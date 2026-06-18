<script setup lang="ts">
// ScreenshotsTab — responsive grid of 16:9 screenshot thumbnails. Clicking
// a thumbnail opens RCarousel in fullscreen (lightbox) mode with prev/next
// navigation, a thumbnail strip, and keyboard / gamepad arrows. Each
// thumbnail carries a hover delete affordance; deletion is confirmed and
// performed by the parent (MediaTab).
import { RBtn, RCarousel } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

// `id` is only present for user-uploaded screenshots (filesystem-backed);
// scraped screenshots shown in the Overview tab carry just a URL and are
// read-only. The delete affordance renders only when `deletable` is set and
// the item has an id.
export type ScreenshotItem = { url: string; id?: number };

const props = defineProps<{
  screenshots: ScreenshotItem[];
  deletable?: boolean;
}>();
const emit = defineEmits<{ delete: [id: number] }>();

const { t } = useI18n();

// RCarousel consumes a flat list of image URLs.
const urls = computed(() => props.screenshots.map((s) => s.url));

const lightboxIndex = ref(0);
const lightboxOpen = ref(false);

function open(index: number) {
  lightboxIndex.value = index;
  lightboxOpen.value = true;
}
function close() {
  lightboxOpen.value = false;
}
</script>

<template>
  <section class="r-v2-det-shots">
    <div
      v-for="(shot, i) in screenshots"
      :key="shot.id ?? shot.url"
      class="r-v2-det-shots__cell"
    >
      <button
        type="button"
        class="r-v2-det-shots__item"
        :aria-label="t('rom.screenshot-num-open', { n: i + 1 })"
        @click="open(i)"
      >
        <img
          :src="shot.url"
          :alt="t('rom.screenshot-num', { n: i + 1 })"
          loading="lazy"
        />
      </button>
      <RBtn
        v-if="deletable && shot.id != null"
        icon="mdi-delete"
        size="small"
        variant="flat"
        color="romm-red"
        class="r-v2-det-shots__delete"
        :aria-label="t('rom.screenshot-num-delete', { n: i + 1 })"
        @click="emit('delete', shot.id)"
      />
    </div>
  </section>

  <RCarousel
    v-if="lightboxOpen"
    v-model="lightboxIndex"
    :items="urls"
    fullscreen
    show-thumbnails
    :aria-label="t('rom.screenshots')"
    @close="close"
  >
    <template #default="{ item, index }">
      <img
        :src="item as string"
        :alt="t('rom.screenshot-num', { n: index + 1 })"
      />
    </template>
    <template #thumbnail="{ item, index }">
      <img
        :src="item as string"
        :alt="t('rom.screenshot-num-thumb', { n: index + 1 })"
      />
    </template>
  </RCarousel>
</template>

<style scoped>
.r-v2-det-shots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
  /* Horizontal padding gives the hover-scale (1.02) + drop shadow
     room to render past the leftmost / rightmost thumbnail before
     the overview's scroll container clips them (it has `overflow-y:
     auto`, which clips on X too per the CSS spec). */
  padding: 6px 6px 4px;
}

.r-v2-det-shots__cell {
  position: relative;
}

.r-v2-det-shots__item {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 0;
  padding: 0;
  border-radius: 6px;
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  cursor: pointer;
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-det-shots__item:hover {
  transform: scale(1.02);
  box-shadow: 0 8px 24px color-mix(in srgb, black 35%, transparent);
}
.r-v2-det-shots__item:active {
  transform: scale(0.99);
}
.r-v2-det-shots__item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* Delete affordance — top-right, revealed on cell hover / focus-within.
   Stays visible on touch/pad (no hover) so it's reachable there. */
.r-v2-det-shots__delete {
  position: absolute;
  top: 6px;
  right: 6px;
  opacity: 0;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-det-shots__cell:hover .r-v2-det-shots__delete,
.r-v2-det-shots__cell:focus-within .r-v2-det-shots__delete {
  opacity: 1;
}
html[data-input="touch"] .r-v2-det-shots__delete,
html[data-input="pad"] .r-v2-det-shots__delete {
  opacity: 1;
}
</style>
