<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";

// Props
const collections = storeCollections();
</script>
<template>
  <r-section icon="mdi-bookmark-box-multiple" title="Collections">
    <template #content>
      <v-row no-gutters>
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
            transformScale
            :key="collection.updated_at"
            :collection="collection"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
