<script setup lang="ts">
import CollectionListItem from "@/components/common/Collection/ListItem.vue";
import storeCollections from "@/stores/collections";
import CreateCollectionDialog from "@/components/common/Collection/Dialog/CreateCollection.vue";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const collectionsStore = storeCollections();
const { filteredCollections, searchText } = storeToRefs(collectionsStore);
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
const emitter = inject<Emitter<Events>>("emitter");

async function addCollection() {
  emitter?.emit("showCreateCollectionDialog", null);
}

function clear() {
  searchText.value = "";
}
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="500"
    v-model="activeCollectionsDrawer"
    class="bg-terciary"
  >
    <template #prepend>
      <v-text-field
        v-model="searchText"
        prepend-inner-icon="mdi-filter-outline"
        clearable
        hide-details
        @click:clear="clear"
        @update:model-value=""
        single-line
        :label="t('collection.search-collection')"
        variant="solo-filled"
        rounded="0"
      ></v-text-field>
    </template>
    <v-list lines="two" rounded="0" class="pa-0">
      <collection-list-item
        v-for="collection in filteredCollections"
        :collection="collection"
        with-link
      />
    </v-list>
    <template #append>
      <v-btn
        @click="addCollection()"
        variant="tonal"
        color="romm-accent-1"
        prepend-icon="mdi-plus"
        size="large"
        rounded="0"
        block
        >{{ t("collection.add-collection") }}</v-btn
      >
    </template>
  </v-navigation-drawer>

  <create-collection-dialog />
</template>
