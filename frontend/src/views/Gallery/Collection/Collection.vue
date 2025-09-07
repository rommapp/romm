<script setup lang="ts">
import { storeToRefs } from "pinia";
import storeCollections, {
  type Collection,
  type CollectionType,
} from "@/stores/collections";
import storeRoms from "@/stores/roms";
import BaseCollection from "./BaseCollection.vue";

const collectionsStore = storeCollections();
const { allCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);

function setCurrentCollection(collection: CollectionType) {
  romsStore.setCurrentCollection(collection as Collection);
}
</script>

<template>
  <BaseCollection
    :collections="allCollections"
    :current-collection="currentCollection"
    :set-current-collection="setCurrentCollection"
  />
</template>
