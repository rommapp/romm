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
    class="pt-4 pb-4 bg-terciary"
  >
    <span v-if="!rail" class="text-body-2">{{ platform.name }}</span>
    <template v-slot:prepend>
      <v-avatar :rounded="0" size="40">
        <platform-icon :slug="platform.slug" />
        <div
          class="igdb-icon"
          v-if="!platform.igdb_id"
          title="Not found in IGDB"
        >
          ⚠️
        </div>
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
.igdb-icon {
  position: absolute;
  bottom: 0;
  right: 0;
}
</style>
