<script setup lang="ts">
import { useDisplay } from "vuetify";
import AdminMenu from "@/components/Gallery/AppBar/Collection/AdminMenu.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import CollectionCard from "@/components/common/Collection/Card.vue";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { ref } from "vue";

const { xs } = useDisplay();
const viewportWidth = ref(window.innerWidth);
const auth = storeAuth();
const romsStore = storeRoms();
const { currentCollection } = storeToRefs(romsStore);
const open = ref(false);
</script>

<template>
  <v-app-bar
    id="gallery-app-bar"
    elevation="0"
    density="compact"
    mode="shift"
    app
    fixed
    top
  >
    <template #prepend>
      <v-btn
        :color="open ? 'romm-accent-1' : ''"
        rounded="0"
        @click="open = !open"
        icon="mdi-information"
      ></v-btn>
      <filter-btn />
    </template>
    <filter-text-field v-if="!xs" />
    <template #append>
      <selecting-btn />
      <gallery-view-btn />
      <v-menu location="bottom">
        <template #activator="{ props }">
          <v-btn
            v-if="auth.scopes.includes('collections.write')"
            v-bind="props"
            rounded="0"
            variant="text"
            class="mr-0"
            icon="mdi-dots-vertical"
            @click.stop
          />
        </template>
        <admin-menu />
      </v-menu>
    </template>
  </v-app-bar>

  <v-navigation-drawer
    v-model="open"
    floating
    mobile
    :width="xs ? viewportWidth : '500'"
    v-if="currentCollection"
  >
    <v-row no-gutters class="justify-center align-center my-4">
      <v-col style="max-width: 240px">
        <collection-card
          :key="currentCollection.updated_at"
          :collection="currentCollection"
        />
      </v-col>
    </v-row>
    <v-row no-gutters>
      <v-col cols="12">
        <v-card class="mt-4 mx-4 bg-terciary fill-width" elevation="0">
          <v-card-text class="pa-4 text-center">
            <p class="text-h6">
              {{ currentCollection.name }}
            </p>
            <p class="text-caption-1">
              {{ currentCollection.description }}
            </p>
            <p class="text-caption-1">
              is public: {{ currentCollection.is_public }}
            </p>
            <p class="text-caption-1">
              roms: {{ currentCollection.rom_count }}
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-navigation-drawer>

  <filter-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
