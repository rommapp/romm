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

const collectionInfoFields = [
  {
    key: "name",
    label: "Name",
  },
  {
    key: "description",
    label: "Description",
  },
  {
    key: "rom_count",
    label: "Roms",
  },
];
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
    <v-row no-gutters class="text-center justify-center align-center mt-2">
      <v-col style="max-width: 240px">
        <collection-card
          :key="currentCollection.updated_at"
          :collection="currentCollection"
        />
      </v-col>
    </v-row>
    <v-row no-gutters class="mt-4">
      <v-col cols="12">
        <v-card class="mx-4 bg-terciary" elevation="0">
          <v-card-text class="pa-4">
            <template
              v-for="(field, index) in collectionInfoFields"
              :key="field.key"
            >
              <div
                v-if="
                  currentCollection[field.key as keyof typeof currentCollection]
                "
                :class="{ 'mt-4': index !== 0 }"
              >
                <p class="text-subtitle-1 text-decoration-underline">
                  {{ field.label }}
                </p>
                <p class="text-subtitle-2">
                  {{
                    currentCollection[
                      field.key as keyof typeof currentCollection
                    ]
                  }}
                </p>
              </div>
            </template>
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
