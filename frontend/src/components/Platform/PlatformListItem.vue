<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import type { Platform } from "@/stores/platforms";

// Props
defineProps<{ platform: Platform; rail: boolean }>();
</script>

<template>
  <v-list-item
    :to="{ name: 'platform', params: { platform: platform.id } }"
    :value="platform.slug"
    :key="platform.slug"
    class="bg-terciary"
  >
    <span v-if="!rail" class="text-body-2">{{ platform.name }}</span>
    <template v-slot:prepend>
      <v-avatar :rounded="0" size="40">
        <platform-icon :key="platform.slug" :slug="platform.slug" />
        <v-tooltip
          location="bottom"
          class="tooltip"
          transition="fade-transition"
          text="Not found"
          open-delay="500"
          ><template v-slot:activator="{ props }">
            <div
              v-bind="props"
              class="not-found-icon"
              v-if="!platform.igdb_id && !platform.moby_id"
            >
              ⚠️
            </div></template
          ></v-tooltip
        >
      </v-avatar>
    </template>
    <template v-slot:append>
      <v-chip v-if="!rail" class="ml-4 bg-chip" size="x-small" label>
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
