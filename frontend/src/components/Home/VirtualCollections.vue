<script setup lang="ts">
import VirtualCollectionCard from "@/components/common/Collection/Virtual/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const collections = storeCollections();
const gridCollections = isNull(localStorage.getItem("settings.gridCollections"))
  ? true
  : localStorage.getItem("settings.gridCollections") === "true";
</script>
<template>
  <r-section
    icon="mdi-bookmark-box-multiple"
    :title="t('common.virtual-collections')"
  >
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridCollections }"
        no-gutters
      >
        <v-col
          v-for="collection in collections.virtualCollections"
          :key="collection.name"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <virtual-collection-card
            show-rom-count
            show-title
            transform-scale
            :key="collection.id"
            :collection="collection"
            with-link
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
