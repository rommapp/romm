<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
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
  <r-section icon="mdi-bookmark-box-multiple" :title="t('common.collections')">
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridCollections,
          'py-2': true,
        }"
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
            :key="collection.updated_at"
            :collection="collection"
            with-link
            title-on-hover
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
