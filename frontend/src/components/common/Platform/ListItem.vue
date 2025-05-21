<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import { ROUTES } from "@/plugins/router";
import type { Platform } from "@/stores/platforms";

// Props
withDefaults(
  defineProps<{
    platform: Platform;
    withLink?: boolean;
    showRomCount?: boolean;
  }>(),
  {
    withLink: false,
    showRomCount: true,
  },
);
</script>

<template>
  <v-list-item
    v-bind="{
      ...(withLink
        ? {
            to: { name: ROUTES.PLATFORM, params: { platform: platform.id } },
          }
        : {}),
    }"
    :value="platform.slug"
    rounded
    density="compact"
    class="my-1 py-2"
  >
    <template #prepend>
      <platform-icon
        :slug="platform.slug"
        :name="platform.name"
        :fs-slug="platform.fs_slug"
        :size="40"
      >
        <v-tooltip
          location="bottom"
          class="tooltip"
          transition="fade-transition"
          text="Not found"
          open-delay="500"
          ><template #activator="{ props }">
            <div
              v-if="!platform.igdb_id && !platform.moby_id && !platform.ss_id"
              v-bind="props"
              class="not-found-icon"
            >
              ⚠️
            </div>
          </template>
        </v-tooltip></platform-icon
      >
    </template>
    <v-row no-gutters
      ><v-col
        ><span class="text-body-1">{{ platform.display_name }}</span></v-col
      ></v-row
    >
    <v-row no-gutters>
      <v-col>
        <span class="text-caption text-grey">{{ platform.fs_slug }}</span>
      </v-col>
    </v-row>
    <template v-if="showRomCount" #append>
      <v-chip class="ml-2" size="x-small" label>
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
