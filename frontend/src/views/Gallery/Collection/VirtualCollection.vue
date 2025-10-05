<script setup lang="ts">
import { storeToRefs } from "pinia";
import storeCollections, {
  type VirtualCollection,
  type CollectionType,
} from "@/stores/collections";
import storeRoms from "@/stores/roms";
import BaseCollection from "./BaseCollection.vue";

const collectionsStore = storeCollections();
const { virtualCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { currentVirtualCollection } = storeToRefs(romsStore);

function setCurrentVirtualCollection(collection: CollectionType) {
  romsStore.setCurrentVirtualCollection(collection as VirtualCollection);
}
</script>

<template>
  <BaseCollection
    :collections="virtualCollections"
    :current-collection="currentVirtualCollection"
    :set-current-collection="setCurrentVirtualCollection"
  />
</template>
