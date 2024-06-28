<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import storeCollections from "@/stores/collections";
import { useDisplay } from "vuetify";

// Props
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const collectionsStore = storeCollections();
const { filteredCollections, searchText } = storeToRefs(collectionsStore);
const { activeCollectionsDrawer } = storeToRefs(navigationStore);

// Functions
function clear() {
  searchText.value = "";
}
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="400"
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
        label="Search collection"
        variant="solo-filled"
        rounded="0"
      ></v-text-field>
    </template>
    <v-list lines="two" rounded="0" class="pa-0">
      <v-list-item
        v-for="collection in filteredCollections"
        :to="{ name: 'collection', params: { collection: collection.id } }"
        :value="collection"
      >
        <v-row no-gutters
          ><v-col
            ><span class="text-body-1">{{ collection.name }}</span></v-col
          ></v-row
        >
        <v-row no-gutters>
          <v-col>
            <span class="text-caption text-grey">{{
              collection.description
            }}</span>
          </v-col>
        </v-row>
        <template #append>
          <v-chip class="ml-2" size="x-small" label>
            {{ collection.rom_count }}
          </v-chip>
        </template>
      </v-list-item>
    </v-list>
    <template #append>
      <v-btn
        variant="tonal"
        color="romm-accent-1"
        prepend-icon="mdi-plus"
        size="large"
        block
        >Add Collection</v-btn
      >
    </template>
  </v-navigation-drawer>
</template>
