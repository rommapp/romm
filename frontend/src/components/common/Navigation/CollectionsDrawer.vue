<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="400"
    v-model="activeCollectionsDrawer"
    class="bg-terciary"
  >
    <v-list lines="two" rounded="0" class="pa-0">
      <v-list-item
        v-for="collection in [
          {
            name: 'Favourites',
            description: 'My favourites collection',
            rom_count: 10,
            id: 0,
          },
          {
            name: 'Nintendo',
            description: 'Nintendo collection',
            rom_count: 7,
            id: 1,
          },
          {
            name: 'Sony',
            description: 'Sony collection',
            rom_count: 20,
            id: 2,
          },
        ]"
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
  </v-navigation-drawer>
</template>
