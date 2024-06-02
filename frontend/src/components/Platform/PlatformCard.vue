<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import PlatformIcon from "./PlatformIcon.vue";

defineProps<{ platform: Platform }>();
</script>

<template>
  <router-link
    id="router-link"
    :to="{ name: 'platform', params: { platform: platform.id } }"
  >
    <v-hover v-slot="{ isHovering, props }">
      <v-card
        v-bind="props"
        class="bg-terciary"
        :class="{ 'on-hover': isHovering }"
        :elevation="isHovering ? 20 : 3"
      >
        <v-card-text>
          <v-row class="pa-1 justify-center bg-primary">
            <div
              :title="platform.name?.toString()"
              class="px-2 text-truncate text-caption"
            >
              {{ platform.name }}
            </div>
          </v-row>
          <v-row class="pa-1 justify-center">
            <v-avatar
              :rounded="0"
              size="105"
              class="mt-2"
            >
              <platform-icon
                :key="platform.slug"
                :slug="platform.slug"
              />
            </v-avatar>
            <v-chip
              class="bg-chip position-absolute"
              size="x-small"
              style="bottom: 1rem; right: 1rem"
              label
            >
              {{ platform.rom_count }}
            </v-chip>
          </v-row>
        </v-card-text>
      </v-card>
    </v-hover>
  </router-link>
</template>

<style scoped>
#router-link {
  text-decoration: none;
  color: inherit;
}
.v-card {
  transition-property: all;
  transition-duration: 0.1s;
}
.v-card.on-hover {
  transform: scale(1.05);
}
</style>
