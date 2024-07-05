<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import RAvatar from "@/components/common/Collection/RAvatar.vue";

// Props
defineProps<{ collection: Collection }>();
</script>

<template>
  <v-list-item
    :key="collection.id"
    :to="{ name: 'collection', params: { collection: collection.id } }"
    :value="collection.name"
  >
    <template #prepend>
      <r-avatar :collection="collection" />
    </template>
    <v-row no-gutters
      ><v-col
        ><span class="text-body-1">{{ collection.name }}</span></v-col
      ></v-row
    >
    <v-row no-gutters>
      <v-col>
        <span class="text-caption text-grey">{{ collection.description }}</span>
      </v-col>
    </v-row>
    <template #append>
      <v-chip class="ml-2" size="x-small" label>
        {{ collection.rom_count }}
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
