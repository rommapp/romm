<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import CollectionCover from "@/components/common/Collection/Cover.vue";

defineProps<{ collection: Collection }>();
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      class="bg-terciary transform-scale"
      :class="{ 'on-hover': isHovering }"
      :elevation="isHovering ? 20 : 3"
      :to="{ name: 'collection', params: { collection: collection.id } }"
    >
      <v-card-text>
        <v-row class="pa-1 justify-center bg-primary">
          <div
            :title="collection.name?.toString()"
            class="px-2 text-truncate text-caption"
          >
            {{ collection.name }}
          </div>
        </v-row>
        <v-row>
          <collection-cover :collection="collection" />
          <v-chip
            class="bg-chip position-absolute"
            size="x-small"
            style="bottom: 0.5rem; right: 0.5rem"
            label
          >
            {{ collection.rom_count }}
          </v-chip>
        </v-row>
      </v-card-text>
    </v-card>
  </v-hover>
</template>
