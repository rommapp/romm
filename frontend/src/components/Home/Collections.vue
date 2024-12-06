<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";
import { isNull } from "lodash";

// Props
const collections = storeCollections();
const wrapCollections = isNull(localStorage.getItem("settings.wrapCollections"))
  ? true
  : localStorage.getItem("settings.wrapCollections") === "true";
</script>
<template>
  <r-section icon="mdi-bookmark-box-multiple" title="Collections">
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': wrapCollections }"
        no-gutters
      >
        <v-col
          v-for="collection in collections.allCollections"
          :key="collection.name"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <collection-card
            show-rom-count
            show-title
            transform-scale
            :key="collection.updated_at"
            :collection="collection"
            with-link
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
