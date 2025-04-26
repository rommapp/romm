<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";
import { ref } from "vue";

// Props
const { t } = useI18n();
const collections = storeCollections();
const storedCollections = localStorage.getItem("settings.gridCollections");
const gridCollections = ref(
  isNull(storedCollections) ? false : storedCollections === "true",
);
function toggleGridCollections() {
  gridCollections.value = !gridCollections.value;
  localStorage.setItem(
    "settings.gridCollections",
    gridCollections.value.toString(),
  );
}
</script>
<template>
  <r-section icon="mdi-bookmark-box-multiple" :title="t('common.collections')">
    <template #toolbar-append>
      <v-btn icon rounded="0" @click="toggleGridCollections"
        ><v-icon>{{
          gridCollections ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridCollections,
        }"
        class="pa-1"
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
            transform-scale
            :key="collection.id"
            :collection="collection"
            with-link
            title-on-hover
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
