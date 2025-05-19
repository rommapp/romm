<script setup lang="ts">
import { formatBytes } from "@/utils";

// Props
const props = defineProps<{
  platforms: Array<{ id: number; name: string; filesize: number | string }>;
  total: number;
}>();

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
      <div v-for="platform in props.platforms" :key="platform.id" class="mb-4">
        <div class="d-flex justify-space-between align-center mb-1">
          <span class="ml-2">
            <strong>{{ platform.name }}</strong>
          </span>
          <span class="mr-2">
            {{ formatBytes(Number(platform.filesize)) }}
            ({{ getPercentage(platform.filesize, props.total).toFixed(1) }}%)
          </span>
        </div>
        <v-progress-linear
          :model-value="getPercentage(platform.filesize, props.total)"
          rounded
          :color="idToHexColor(platform.id)"
          height="15"
        />
      </div>
    </v-card-text>
  </v-card>
</template>
