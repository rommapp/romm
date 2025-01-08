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
  },
);
const navigationStore = storeNavigation();
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    rounded="0"
    :color="activeCollectionsDrawer ? 'toplayer' : 'background'"
    @click="navigationStore.switchActiveCollectionsDrawer"
    class="rounded my-1"
    ><v-icon :color="$route.name == 'collection' ? 'primary' : ''"
      >mdi-bookmark-box-multiple</v-icon
    ></v-btn
  >
</template>
