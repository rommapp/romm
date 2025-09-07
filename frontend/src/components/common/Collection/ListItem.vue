<script setup lang="ts">
import { computed } from "vue";
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import { ROUTES } from "@/plugins/router";
import type { CollectionType } from "@/stores/collections";

const props = withDefaults(
  defineProps<{
    collection: CollectionType;
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

const collectionType = computed(() => {
  if ("filter_criteria" in props.collection) return "smart";
  if ("type" in props.collection) return "virtual";
  return "regular";
});

// Determine the correct route for this collection type
const collectionRoute = computed(() => {
  if (!props.withLink || !props.collection) return {};

  if (collectionType.value === "smart") {
    return {
      to: {
        name: ROUTES.SMART_COLLECTION,
        params: { collection: props.collection.id },
      },
    };
  }

  if (collectionType.value === "virtual") {
    return {
      to: {
        name: ROUTES.VIRTUAL_COLLECTION,
        params: { collection: props.collection.id },
      },
    };
  }

  return {
    to: {
      name: ROUTES.COLLECTION,
      params: { collection: props.collection.id },
    },
  };
});
</script>

<template>
  <v-list-item
    v-bind="collectionRoute"
    :value="`${collectionType}-${collection.id}`"
    rounded
    density="compact"
    class="my-1 py-2"
  >
    <template #prepend>
      <RAvatar :size="45" :collection="collection" />
    </template>
    <v-row v-if="withTitle" no-gutters>
      <v-col>
        <span class="text-body-1">{{ collection.name }}</span>
      </v-col>
    </v-row>
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
