<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
  }>(),
  {
    block: false,
  }
);
const navigationStore = storeNavigation();
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    :block="block"
    rounded="0"
    variant="flat"
    :color="activeCollectionsDrawer ? 'terciary' : ''"
    icon
    @click="navigationStore.switchActiveCollectionsDrawer"
    ><v-icon :color="$route.name == 'collection' ? 'romm-accent-1' : ''"
      >mdi-bookmark-box-multiple</v-icon
    ></v-btn
  >
</template>
