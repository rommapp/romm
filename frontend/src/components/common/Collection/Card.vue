<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import { computed } from "vue";
import { useTheme } from "vuetify";

// Props
const props = withDefaults(
  defineProps<{
    collection: Collection;
    transformScale?: boolean;
    titleOnHover?: boolean;
    showRomCount?: boolean;
    withLink?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    titleOnHover: false,
    showRomCount: false,
    withLink: false,
    src: "",
  },
);

const theme = useTheme();
const galleryViewStore = storeGalleryView();

const hashedName = computed(() => {
  let h = 0;
  for (let i = 0; i < props.collection.name.length; i++) {
    h = Math.imul(h ^ props.collection.name.charCodeAt(i), 100);
  }
  return Math.abs(h);
});

const translatedBGs = computed(() => {
  return {
    left: {
      x: -150 + (hashedName.value % 100),
      y: -75 + (hashedName.value % 50),
    },
    right: {
      x: 250 - (hashedName.value % 100),
      y: 150 - (hashedName.value % 50),
    },
  };
});

const bgRotation = computed(() => {
  return hashedName.value % 60;
});

const svgCollection = computed(() => {
  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" preserveAspectRatio="none" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform:translate(${translatedBGs.value.left.x}px,${translatedBGs.value.left.y}px);rotate: ${bgRotation.value}deg;"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform:translate(${translatedBGs.value.right.x}px,${translatedBGs.value.right.y}px);rotate: ${bgRotation.value}deg;"/><path d="M201.212 336.962h-26.135v182.942c0 14.374 11.76 26.134 26.135 26.134h182.942v-26.134H201.212zm209.076-52.27H253.481c-14.374 0-26.135 11.76-26.135 26.135v156.808c0 14.374 11.76 26.134 26.135 26.134h156.807c14.375 0 26.135-11.76 26.135-26.134V310.827c0-14.374-11.76-26.135-26.135-26.135m0 130.673-32.668-19.6-32.668 19.6V310.827h65.336z" style="fill:#f9f9f9;stroke-width:13.0673"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  console.log(svgString);

  const blob = new Blob([svgString], { type: "image/svg+xml" });
  return URL.createObjectURL(blob);
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-card
      v-bind="{
        ...hoverProps,
        ...(withLink && collection
          ? {
              to: { name: 'collection', params: { collection: collection.id } },
            }
          : {}),
      }"
      :class="{
        'on-hover': isHovering,
        'transform-scale': transformScale,
      }"
      :elevation="isHovering && transformScale ? 20 : 3"
    >
      <v-img
        cover
        :src="
          src
            ? src
            : collection.has_cover
              ? `/assets/romm/resources/${collection.path_cover_l}?ts=${collection.updated_at}`
              : collection.name && collection.name.toLowerCase() == 'favourites'
                ? `/assets/default/cover/${theme.global.name.value}_fav.svg`
                : svgCollection
        "
        :lazy-src="
          src
            ? src
            : collection.has_cover
              ? `/assets/romm/resources/${collection.path_cover_s}?ts=${collection.updated_at}`
              : collection.name && collection.name.toLowerCase() == 'favourites'
                ? `/assets/default/cover/${theme.global.name.value}_fav.svg`
                : svgCollection
        "
        :aspect-ratio="galleryViewStore.defaultAspectRatioCollection"
      >
        <template v-if="titleOnHover">
          <v-expand-transition>
            <div
              v-if="isHovering || !collection.has_cover"
              class="translucent-dark text-caption text-center text-white"
            >
              <v-list-item>{{ collection.name }}</v-list-item>
            </div>
          </v-expand-transition>
        </template>

        <div class="position-absolute append-inner">
          <slot name="append-inner"></slot>
        </div>

        <template #error>
          <v-img
            :src="`/assets/default/cover/${theme.global.name.value}_missing_cover.svg`"
            cover
            :aspect-ratio="galleryViewStore.defaultAspectRatioCollection"
          ></v-img>
        </template>
        <template #placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular
              :width="2"
              :size="40"
              color="primary"
              indeterminate
            />
          </div>
        </template>
      </v-img>
      <v-chip
        v-if="showRomCount"
        class="bg-background position-absolute"
        size="x-small"
        style="bottom: 0.5rem; right: 0.5rem"
        label
      >
        {{ collection.rom_count }}
      </v-chip>
    </v-card>
  </v-hover>
</template>
<style scoped>
.append-inner {
  bottom: 0rem;
  right: 0rem;
}
</style>
