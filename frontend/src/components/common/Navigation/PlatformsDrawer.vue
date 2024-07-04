<script setup lang="ts">
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import platformApi from "@/services/api/platform";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted } from "vue";
import { useDisplay } from "vuetify";

// Props
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const { filteredPlatforms, searchText } = storeToRefs(platformsStore);
const { activePlatformsDrawer } = storeToRefs(navigationStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
function clear() {
  searchText.value = "";
}

onMounted(async () => {
  navigationStore.resetDrawers();
  await platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    @update:model-value="clear"
    width="400"
    v-model="activePlatformsDrawer"
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
        label="Search platform"
        variant="solo-filled"
        rounded="0"
      ></v-text-field>
    </template>
    <v-list lines="two" rounded="0" class="pa-0">
      <platform-list-item
        v-for="platform in filteredPlatforms"
        :key="platform.slug"
        :platform="platform"
        class="py-4"
      />
    </v-list>
  </v-navigation-drawer>
</template>
