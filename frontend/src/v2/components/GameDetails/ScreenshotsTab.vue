<script setup lang="ts">
// ScreenshotsTab — responsive grid of 16:9 screenshot thumbnails. Clicking
// a thumbnail opens RCarousel in fullscreen (lightbox) mode with prev/next
// navigation, a thumbnail strip, and keyboard / gamepad arrows.
import { RCarousel } from "@v2/lib";
import { ref } from "vue";

defineOptions({ inheritAttrs: false });

defineProps<{ urls: string[] }>();

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
    <button
      v-for="(src, i) in urls"
      :key="src"
      type="button"
      class="r-v2-det-shots__item"
      :aria-label="`Open screenshot ${i + 1}`"
      @click="open(i)"
    >
      <img :src="src" :alt="`Screenshot ${i + 1}`" loading="lazy" />
    </button>
  </section>

  <RCarousel
    v-if="lightboxOpen"
    v-model="lightboxIndex"
    :items="urls"
    fullscreen
    show-thumbnails
    aria-label="Screenshot lightbox"
    @close="close"
  >
    <template #default="{ item, index }">
      <img :src="item as string" :alt="`Screenshot ${index + 1}`" />
    </template>
    <template #thumbnail="{ item, index }">
      <img :src="item as string" :alt="`Screenshot ${index + 1} thumbnail`" />
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

.r-v2-det-shots__item {
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
</style>
