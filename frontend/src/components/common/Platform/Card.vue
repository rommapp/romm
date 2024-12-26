<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import PlatformIcon from "@/components/common/Platform/Icon.vue";

defineProps<{ platform: Platform }>();
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      class="bg-terciary transform-scale"
      :class="{ 'on-hover': isHovering }"
      :elevation="isHovering ? 20 : 3"
      :to="{ name: 'platform', params: { platform: platform.id } }"
    >
      <v-card-text>
        <v-row class="pa-1 justify-center bg-primary">
          <div
            :title="platform.display_name"
            class="px-2 text-truncate text-caption"
          >
            <span>{{ platform.display_name }}</span>
          </div>
        </v-row>
        <v-row class="pa-1 justify-center">
          <platform-icon
            :key="platform.slug"
            :slug="platform.slug"
            :name="platform.name"
            :size="105"
            class="mt-2"
          />
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
</template>
