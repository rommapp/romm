<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { DetailedRom } from "@/stores/roms";
import { useDisplay } from "vuetify";

defineProps<{ rom: DetailedRom }>();
const { xs } = useDisplay();
const galleryFilter = storeGalleryFilter();
</script>
<template>
  <v-divider class="mx-2 my-4" />
  <template v-for="filter in galleryFilter.filters">
    <v-row v-if="rom[filter].length > 0" class="align-center my-3" no-gutters>
      <v-col cols="3" xl="2" class="text-capitalize">
        <span>{{ filter }}</span>
      </v-col>
      <v-col>
        <v-chip v-for="value in rom[filter]" class="my-1 mr-2" label>
          {{ value }}
        </v-chip>
      </v-col>
    </v-row>
  </template>
  <template v-if="rom.summary != ''">
    <v-divider class="mx-2 my-4" />
    <v-row no-gutters>
      <v-col class="text-caption">
        <p v-html="rom.summary"></p>
      </v-col>
    </v-row>
  </template>
  <template v-if="rom.merged_screenshots.length > 0">
    <v-divider class="mx-2 my-4" />
    <v-row no-gutters>
      <v-col>
        <v-carousel
          hide-delimiter-background
          delimiter-icon="mdi-square"
          class="bg-primary"
          show-arrows="hover"
          hide-delimiters
          progress="terciary"
          :height="xs ? '300' : '400'"
        >
          <template #prev="{ props }">
            <v-btn
              icon="mdi-chevron-left"
              class="translucent"
              @click="props.onClick"
            />
          </template>
          <v-carousel-item
            v-for="screenshot_url in rom.merged_screenshots"
            :src="screenshot_url"
          />
          <template #next="{ props }">
            <v-btn
              icon="mdi-chevron-right"
              class="translucent"
              @click="props.onClick"
            />
          </template>
        </v-carousel>
      </v-col>
    </v-row>
  </template>
</template>