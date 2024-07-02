<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import { useTheme } from "vuetify";

withDefaults(
  defineProps<{
    collection: Collection;
    transformScale?: boolean;
    showTitle?: boolean;
    showRomCount?: boolean;
    withLink?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    showTitle: false,
    showRomCount: false,
    withLink: true,
    src: "",
  }
);
const theme = useTheme();
</script>

<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-card
      v-bind="hoverProps"
      :class="{
        'on-hover': isHovering,
        'transform-scale': transformScale,
      }"
      :elevation="isHovering && transformScale ? 20 : 3"
      :to="
        withLink && collection
          ? { name: 'collection', params: { collection: collection.id } }
          : ''
      "
    >
      <v-row
        v-if="showTitle"
        no-gutters
        class="py-1 px-2 text-truncate text-center text-caption"
      >
        <v-col>
          {{ collection.name }}
        </v-col>
      </v-row>
      <v-img
        cover
        :src="
          src
            ? src
            : collection.path_cover_l
            ? collection.path_cover_l
            : `/assets/default/cover/big_${theme.global.name.value}_collection.png`
        "
        :lazy-src="
          src
            ? src
            : collection.path_cover_s
            ? collection.path_cover_s
            : `/assets/default/cover/small_${theme.global.name.value}_collection.png`
        "
        :aspect-ratio="2 / 3"
      >
        <div class="position-absolute append-inner">
          <slot name="append-inner"></slot>
        </div>

        <template #error>
          <v-img
            :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
            cover
            :aspect-ratio="2 / 3"
          ></v-img>
        </template>
        <template #placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular
              :width="2"
              :size="40"
              color="romm-accent-1"
              indeterminate
            />
          </div>
        </template>
      </v-img>
      <v-chip
        v-if="showRomCount"
        class="bg-chip position-absolute"
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
  bottom: -0.1rem;
  right: -0.3rem;
}
</style>
