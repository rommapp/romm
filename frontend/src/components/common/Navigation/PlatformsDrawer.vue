<script setup lang="ts">
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const { filteredPlatforms, searchText } = storeToRefs(platformsStore);
const { activePlatformsDrawer } = storeToRefs(navigationStore);

function clear() {
  searchText.value = "";
}
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    @update:model-value="clear"
    width="500"
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
        :label="t('platform.search-platform')"
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
