<script setup lang="ts">
import type {
  Collection,
  VirtualCollection,
  SmartCollection,
} from "@/stores/collections";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import { ROUTES } from "@/plugins/router";

// Props
const props = withDefaults(
  defineProps<{
    collection: Collection | VirtualCollection | SmartCollection;
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

// Determine the correct route for this collection type
const getCollectionRoute = () => {
  if (!props.withLink || !props.collection) return {};

  // Check if it's a smart collection (has filter_criteria property)
  if ("filter_criteria" in props.collection) {
    return {
      name: ROUTES.SMART_COLLECTION,
      params: { collection: props.collection.id },
    };
  }

  // Default to regular collection route for both regular and virtual collections
  return {
    name: ROUTES.COLLECTION,
    params: { collection: props.collection.id },
  };
};
</script>

<template>
  <v-list-item
    v-bind="getCollectionRoute()"
    :value="collection.id"
    rounded
    density="compact"
    class="my-1 py-2"
  >
    <template #prepend>
      <r-avatar :size="45" :collection="collection" />
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
