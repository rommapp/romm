<script setup lang="ts">
import BaseCollection from "./BaseCollection.vue";
import storeCollections, {
  type Collection,
  type CollectionType,
} from "@/stores/collections";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";

const collectionsStore = storeCollections();
const { allCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);

function setCurrentCollection(collection: CollectionType) {
  romsStore.setCurrentCollection(collection as Collection);
}
</script>

<template>
  <base-collection
    :collections="allCollections"
    :current-collection="currentCollection"
    :set-current-collection="setCurrentCollection"
  ></base-collection>
</template>
