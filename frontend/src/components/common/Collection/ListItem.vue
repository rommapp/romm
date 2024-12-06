<script setup lang="ts">
import type { Collection } from "@/stores/collections";
import RAvatar from "@/components/common/Collection/RAvatar.vue";

// Props
withDefaults(
  defineProps<{
    collection: Collection;
    withTitle?: boolean;
    withDescription?: boolean;
    withRomCount?: boolean;
    withLink?: boolean;
  }>(),
  {
    withTitle: true,
    withDescription: true,
    withRomCount: true,
    withLink: false,
  },
);
</script>

<template>
  <v-list-item
    :key="collection.id"
    v-bind="{
      ...(withLink && collection
        ? {
            to: { name: 'collection', params: { collection: collection.id } },
          }
        : {}),
    }"
    :value="collection.name"
    class="py-1 pl-1"
  >
    <template #prepend>
      <r-avatar :size="75" :collection="collection" />
    </template>
    <v-row v-if="withTitle" no-gutters
      ><v-col
        ><span class="text-body-1">{{ collection.name }}</span></v-col
      ></v-row
    >
    <v-row v-if="withDescription" no-gutters>
      <v-col>
        <span class="text-caption text-grey">{{ collection.description }}</span>
      </v-col>
    </v-row>
    <template v-if="withRomCount" #append>
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
