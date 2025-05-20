<script setup lang="ts">
import { formatBytes } from "@/utils";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";

// Props
const props = defineProps<{
  total_filesize: number;
}>();

const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);

// Functions
function getPercentage(filesize: number | string, total: number): number {
  const size = typeof filesize === "string" ? parseInt(filesize, 10) : filesize;
  if (!total || isNaN(size)) return 0;
  return (size / total) * 100;
}

function idToHexColor(id: number): string {
  const knuthHash = 2654435761;
  const hex = ((id * knuthHash) >>> 0).toString(16).padStart(6, "0");
  return `#${hex.slice(0, 6)}`;
}
</script>

<template>
  <v-card>
    <v-card-text>
      <div
        v-for="(platform, idx) in filteredPlatforms"
        :class="{ 'mb-8': idx !== filteredPlatforms.length - 1 }"
      >
        <v-row no-gutters class="d-flex justify-space-between align-center">
          <v-col cols="6">
            <platform-list-item
              :platform="platform"
              :key="platform.slug"
              :showRomCount="false"
            />
          </v-col>
          <v-col cols="6" class="text-right">
            <v-list-item>
              <v-list-item-title class="text-body-2">
                {{ formatBytes(Number(platform.fs_size_bytes)) }}
                ({{
                  getPercentage(
                    platform.fs_size_bytes,
                    props.total_filesize,
                  ).toFixed(1)
                }}%)
              </v-list-item-title>
              <v-list-item-subtitle class="text-right mt-1">
                {{ platform.rom_count }} roms
              </v-list-item-subtitle>
            </v-list-item>
          </v-col>
        </v-row>
        <v-progress-linear
          :model-value="
            getPercentage(platform.fs_size_bytes, props.total_filesize)
          "
          rounded
          color="primary"
          height="8"
        />
      </div>
    </v-card-text>
  </v-card>
</template>
