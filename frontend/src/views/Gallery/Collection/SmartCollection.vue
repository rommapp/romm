<script setup lang="ts">
import BaseCollection from "./BaseCollection.vue";
import storeCollections, {
  type SmartCollection,
  type CollectionType,
} from "@/stores/collections";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";

const collectionsStore = storeCollections();
const { smartCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { currentSmartCollection } = storeToRefs(romsStore);

function setCurrentSmartCollection(collection: CollectionType) {
  romsStore.setCurrentSmartCollection(collection as SmartCollection);
}
</script>

<template>
  <base-collection
    :collections="smartCollections"
    :current-collection="currentSmartCollection"
    :set-current-collection="setCurrentSmartCollection"
  ></base-collection>
</template>
