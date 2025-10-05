<script setup lang="ts">
import { storeToRefs } from "pinia";
import storeCollections, {
  type SmartCollection,
  type CollectionType,
} from "@/stores/collections";
import storeRoms from "@/stores/roms";
import BaseCollection from "./BaseCollection.vue";

const collectionsStore = storeCollections();
const { smartCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { currentSmartCollection } = storeToRefs(romsStore);

function setCurrentSmartCollection(collection: CollectionType) {
  romsStore.setCurrentSmartCollection(collection as SmartCollection);
}
</script>

<template>
  <BaseCollection
    :collections="smartCollections"
    :current-collection="currentSmartCollection"
    :set-current-collection="setCurrentSmartCollection"
  />
</template>
