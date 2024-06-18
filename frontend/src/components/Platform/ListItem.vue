<script setup lang="ts">
import PlatformIcon from "@/components/Platform/Icon.vue";
import type { Platform } from "@/stores/platforms";

// Props
defineProps<{ platform: Platform; rail: boolean }>();
</script>

<template>
  <v-list-item
    :key="platform.slug"
    :to="{ name: 'platform', params: { platform: platform.id } }"
    :value="platform.slug"
    class="bg-terciary"
  >
    <v-row no-gutters v-if="!rail"
      ><v-col
        ><span class="text-body-2">{{ platform.name }}</span></v-col
      ></v-row
    >
    <v-row no-gutters v-if="!rail"
      ><v-col
        ><span class="text-caption text-grey">{{
          platform.fs_slug
        }}</span></v-col
      ></v-row
    >

    <template #prepend>
      <platform-icon :key="platform.slug" :slug="platform.slug"
        ><v-tooltip
          location="bottom"
          class="tooltip"
          transition="fade-transition"
          text="Not found"
          open-delay="500"
          ><template #activator="{ props }">
            <div
              v-if="!platform.igdb_id && !platform.moby_id"
              v-bind="props"
              class="not-found-icon"
            >
              ⚠️
            </div>
          </template>
        </v-tooltip></platform-icon
      >
    </template>
    <template #append>
      <v-chip v-if="!rail" class="ml-3 bg-chip" size="x-small" label>
        {{ platform.rom_count }}
      </v-chip>
    </template>
  </v-list-item>
</template>

<style scoped>
.not-found-icon {
  position: absolute;
  bottom: 0;
  right: 0;
}
</style>
